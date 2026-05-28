from flask import Flask, request, redirect, render_template_string, session
import json, os, subprocess, time

app = Flask(__name__)
app.secret_key = "troque_essa_chave"
app.permanent_session_lifetime = 3600

RULES_FILE = "/opt/port-panel/rules.json"
AUTH_FILE = "/opt/port-panel/auth.json"
HAPROXY_CFG = "/etc/haproxy/haproxy.cfg"
PUBLIC_IP = "76.13.164.143"

def load_auth():
    if not os.path.exists(AUTH_FILE):
        auth = {"user": "admin", "pass": "admin"}
        with open(AUTH_FILE, "w") as f:
            json.dump(auth, f)
        return auth
    with open(AUTH_FILE, "r") as f:
        return json.load(f)

def load_rules():
    if not os.path.exists(RULES_FILE):
        return []
    with open(RULES_FILE, "r") as f:
        return json.load(f)

def save_rules(rules):
    with open(RULES_FILE, "w") as f:
        json.dump(rules, f, indent=2)

def generate_haproxy(rules):
    cfg = """
global
    log /dev/log local0
    maxconn 4096
    daemon

defaults
    log global
    mode tcp
    option tcplog
    timeout connect 10s
    timeout client 1h
    timeout server 1h

frontend dummy_frontend
    bind 127.0.0.1:65535
    mode tcp
    default_backend dummy_backend

backend dummy_backend
    mode tcp
    server dummy 127.0.0.1:65534

"""
    for i, r in enumerate(rules):
        if not r.get("enabled", True):
            continue

        name = r["name"].replace(" ", "_").replace("-", "_")
        public_port = r["public_port"]
        target_ip = r["target_ip"]
        target_port = r["target_port"]

        cfg += f"""
frontend fe_{i}_{name}_{public_port}
    bind *:{public_port}
    mode tcp
    default_backend be_{i}_{name}_{public_port}

backend be_{i}_{name}_{public_port}
    mode tcp
    server srv1 {target_ip}:{target_port} check
"""
    with open(HAPROXY_CFG, "w") as f:
        f.write(cfg)

def sync_firewall(rules):

    subprocess.run("ufw --force enable", shell=True)

    status = subprocess.run(
        "ufw status numbered",
        shell=True,
        capture_output=True,
        text=True
    ).stdout

    existing_ports = []

    for line in status.splitlines():
        if "/tcp" in line:
            try:
                port = line.split("/tcp")[0].split()[-1]
                existing_ports.append(port)
            except:
                pass

    active_ports = []

    for r in rules:
        if r.get("enabled", True):
            active_ports.append(str(r["public_port"]))

    for port in existing_ports:

        if port in ["22", "22777", "8088"]:
            continue

        if port not in active_ports:
            subprocess.run(
                f"ufw delete allow {port}/tcp",
                shell=True,
                capture_output=True
            )

    for port in active_ports:
        subprocess.run(
            f"ufw allow {port}/tcp",
            shell=True,
            capture_output=True
        )

def port_in_use(port):
    port = str(port)

    check = subprocess.run(
        f"ss -tulpn | grep -E '[:.]({port})\\s'",
        shell=True,
        capture_output=True,
        text=True
    )

    if check.stdout.strip():
        return True

    rules = load_rules()
    for r in rules:
        if str(r.get("public_port")) == port and r.get("enabled", True):
            return True

    return False


def port_in_use_except_current(port, current_index):
    port = str(port)

    rules = load_rules()
    for idx, r in enumerate(rules):
        if idx != current_index and str(r.get("public_port")) == port and r.get("enabled", True):
            return True

    check = subprocess.run(
        f"ss -tulpn | grep -E '[:.]({port})\\s'",
        shell=True,
        capture_output=True,
        text=True
    )

    if check.stdout.strip():
        for line in check.stdout.splitlines():
            if "haproxy" in line:
                continue
            return True

    return False


def error_page(msg):
    return f"""
    <div style="font-family:Arial;max-width:500px;margin:80px auto;">
        <h2>Erro</h2>
        <p>{msg}</p>
        <a href="/">Voltar</a>
    </div>
    """


def apply_haproxy():

    rules = load_rules()

    sync_firewall(rules)

    generate_haproxy(rules)

    test = subprocess.run(
        ["haproxy", "-c", "-f", HAPROXY_CFG],
        capture_output=True,
        text=True
    )

    if test.returncode != 0:
        raise Exception(test.stderr or test.stdout)

    subprocess.run(
        ["systemctl", "reload", "haproxy"]
    )

def require_login():
    if not session.get("logged"):
        return False

    now = int(time.time())
    last = session.get("last_activity", now)

    if now - last > 3600:
        session.clear()
        return False

    session["last_activity"] = now
    session.permanent = True
    return True

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Port Forward Panel</title>
    <style>
        body { font-family: Arial; background:#f4f4f4; padding:30px; }
        .box { background:white; padding:20px; border-radius:10px; max-width:1200px; margin:auto; }
        input { padding:8px; margin:4px; }
        button { padding:8px 14px; cursor:pointer; }
        table { width:100%; border-collapse:collapse; margin-top:20px; }
        th, td { border:1px solid #ddd; padding:8px; text-align:left; }
        th { background:#222; color:white; }
        .ok { background:#27ae60; color:white; border:0; }
        .danger { color:#c0392b; }
        .badge { background:#ff432e; color:white; padding:8px 14px; border-radius:5px; font-weight:bold; }
    </style>
</head>
<body>
<div class="box">
    <h2>Port Forward Panel</h2>

    <form method="POST" action="/add">
        <input name="name" placeholder="Nome" required>
        <input name="public_port" placeholder="Porta pública" required>
        <input name="target_ip" placeholder="IP Tailscale destino" required>
        <input name="target_port" placeholder="Porta destino" required>
        <button class="ok">Adicionar e Aplicar</button>
    </form>

    <table>
        <tr>
            <th>Nome</th>
            <th>Acesso Público</th>
            <th>Destino</th>
            <th>Status</th>
            <th>Ações</th>
        </tr>
        {% for r in rules %}
        <tr>
            <td>{{r.name}}</td>
            <td>{{public_ip}}:{{r.public_port}}</td>
            <td>{{r.target_ip}}:{{r.target_port}}</td>
            <td>{{ "Ativo" if r.enabled else "Desativado" }}</td>
            <td>
                <a href="/edit/{{loop.index0}}">Editar</a> |
                <a href="/toggle/{{loop.index0}}">{{ "Desativar" if r.enabled else "Ativar" }}</a> |
                <a class="danger" href="/delete/{{loop.index0}}" onclick="return confirm('Tem certeza que deseja excluir esta regra?' )">Excluir</a>
            </td>
        </tr>
        {% endfor %}
    </table>

    <p>
        <a href="/change-password">Alterar Usuário/Senha</a> |
        <a href="/logout">Sair</a>
    </p>
</div>
</body>
</html>
"""

LOGIN = """
<form method="POST" style="font-family:Arial; max-width:300px; margin:80px auto;">
    <h2>Login</h2>
    <input name="user" placeholder="Usuário" style="width:100%;padding:10px;margin:5px;"><br>
    <input name="pass" type="password" placeholder="Senha" style="width:100%;padding:10px;margin:5px;"><br>
    <button style="padding:10px;width:100%;">Entrar</button>
</form>
"""

@app.route("/")
def index():
    if not require_login():
        return redirect("/login")
    return render_template_string(HTML, rules=load_rules(), public_ip=PUBLIC_IP)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        auth = load_auth()
        if request.form["user"] == auth["user"] and request.form["pass"] == auth["pass"]:
            session["logged"] = True
            session["last_activity"] = int(time.time())
            session.permanent = True
            return redirect("/")
    return LOGIN

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/add", methods=["POST"])
def add():
    if not require_login():
        return redirect("/login")

    public_port = request.form["public_port"]

    if port_in_use(public_port):
        return error_page(f"A porta pública {public_port} já está em uso ou já existe em uma regra ativa.")

    rules = load_rules()
    rules.append({
        "name": request.form["name"],
        "public_port": public_port,
        "target_ip": request.form["target_ip"],
        "target_port": request.form["target_port"],
        "enabled": True
    })
    save_rules(rules)
    apply_haproxy()
    return redirect("/")

@app.route("/edit/<int:i>", methods=["GET", "POST"])
def edit(i):
    if not require_login():
        return redirect("/login")

    rules = load_rules()

    if request.method == "POST":
        new_public_port = request.form["public_port"]

        if port_in_use_except_current(new_public_port, i):
            return error_page(f"A porta pública {new_public_port} já está em uso ou já existe em outra regra ativa.")

        rules[i]["name"] = request.form["name"]
        rules[i]["public_port"] = new_public_port
        rules[i]["target_ip"] = request.form["target_ip"]
        rules[i]["target_port"] = request.form["target_port"]
        save_rules(rules)
        apply_haproxy()
        return redirect("/")

    r = rules[i]
    return f"""
    <form method="POST" style="font-family:Arial;max-width:400px;margin:80px auto;">
        <h2>Editar Regra</h2>
        <input name="name" value="{r['name']}" placeholder="Nome" style="width:100%;padding:10px;margin:5px;"><br>
        <input name="public_port" value="{r['public_port']}" placeholder="Porta pública" style="width:100%;padding:10px;margin:5px;"><br>
        <input name="target_ip" value="{r['target_ip']}" placeholder="IP Tailscale destino" style="width:100%;padding:10px;margin:5px;"><br>
        <input name="target_port" value="{r['target_port']}" placeholder="Porta destino" style="width:100%;padding:10px;margin:5px;"><br>
        <button style="padding:10px;width:100%;">Salvar e Aplicar</button>
        <p><a href="/">Voltar</a></p>
    </form>
    """

@app.route("/toggle/<int:i>")
def toggle(i):
    if not require_login():
        return redirect("/login")

    rules = load_rules()
    rules[i]["enabled"] = not rules[i].get("enabled", True)
    save_rules(rules)
    apply_haproxy()
    return redirect("/")

@app.route("/delete/<int:i>")
def delete(i):
    if not require_login():
        return redirect("/login")

    rules = load_rules()
    rules.pop(i)
    save_rules(rules)
    apply_haproxy()
    return redirect("/")

@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    if not require_login():
        return redirect("/login")

    auth = load_auth()

    if request.method == "POST":
        current = request.form["current"]
        newuser = request.form["newuser"]
        newpass = request.form["newpass"]

        if current == auth["pass"]:
            auth["user"] = newuser
            auth["pass"] = newpass
            with open(AUTH_FILE, "w") as f:
                json.dump(auth, f)
            return '<h2>Alterado com sucesso</h2><a href="/">Voltar</a>'

        return '<h2>Senha atual incorreta</h2><a href="/change-password">Tentar novamente</a>'

    return f"""
    <form method="POST" style="font-family:Arial;max-width:350px;margin:80px auto;">
        <h2>Alterar Usuário e Senha</h2>
        <input type="text" name="newuser" value="{auth['user']}" placeholder="Novo usuário" style="width:100%;padding:10px;margin:5px;"><br>
        <input type="password" name="current" placeholder="Senha atual" style="width:100%;padding:10px;margin:5px;"><br>
        <input type="password" name="newpass" placeholder="Nova senha" style="width:100%;padding:10px;margin:5px;"><br>
        <button style="padding:10px;width:100%;">Salvar</button>
        <p><a href="/">Voltar</a></p>
    </form>
    """

app.run(host="0.0.0.0", port=8088)
