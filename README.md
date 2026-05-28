# Layer4 Forward Panel

Sistema web simples para gerenciamento de redirecionamentos TCP 
Layer 4 utilizando HAProxy e Tailscale.

O projeto permite publicar portas externas de uma VPS e 
redirecionar automaticamente para dispositivos internos conectados 
na rede Tailscale.

Exemplo:

```text
76.13.164.143:22777 → 100.117.193.25:22
```

Ideal para:

* SSH
* RDP
* Oracle
* MySQL
* PostgreSQL
* ERP
* Sistemas internos
* Ambientes protegidos por CGNAT

---

# Como funciona

A VPS recebe conexões externas através de um IP público.

O painel web cria automaticamente regras no HAProxy para 
encaminhar conexões TCP para dispositivos da rede Tailscale.

Fluxo:

```text
Internet
↓
VPS Pública
↓
HAProxy
↓
Rede Tailscale
↓
Servidor interno
```

---

# Tecnologias utilizadas

* Python Flask
* HAProxy
* Tailscale
* UFW Firewall
* Ubuntu Server

---

# Instalação

## 1. Atualizar servidor

```bash
apt update && apt upgrade -y
```

---

## 2. Instalar Tailscale

```bash
curl -fsSL https://tailscale.com/installectar na rede Tailscale:

```bash
tailscale up
```

Verificar IP:

```bash
tailscale ip -4
```

---

## 3. Instalar dependências

```bash
apt install -y \
    haproxy \
    python3 \
    python3-pip \
    ufw
```

---

## 4. Instalar Flask

```bash
pip3 install flask --break-system-packages
```

---

## 5. Criar estrutura do projeto

```bash
mkdir -p /opt/port-panel
```

Copiar:

* app.py
* systemd/port-panel.service

---

## 6. Ativar serviço

```bash
cp systemd/port-panel.service /etc/systemd/system/

systemctl daemon-reload
systemctl enable --noport-panel
```

---

# Segurança

O painel foi projetado para funcionar preferencialmente apenas 
através da rede Tailscale.

Exemplo de firewall:

```bash
ufw allow 22777/tcp
ufw allow from 100.64.0.0/10 to any port 8088 proto tcp
ufw enable
```

Isso permite:

* SSH público
* Painel apenas via Tailscale

---

# Painel Web

Acesso:

```text
http://IP_TAILSCALE:8088
```

Funções:

* Criar redirecionamentos TCP
* Editar regras
* Ativar/desativar regras
* Exclusão com confirmação
* Aplicação automática do HAProxy
* Gerenciaático do firewall
* Logout automático por inatividade
* Alteração de usuário e senha

---

# HAProxy

As regras são geradas automaticamente no arquivo:

```text
/etc/haproxy/haproxy.cfg
```

Toda alteração no painel:

* atualiza firewall
* valida configuração
* recarrega HAProxy automaticamente

---

# Tailscale

Todos os destinos internos devenectados na mesma rede Tailscale.

Exemplo:

```text
100.117.193.25
100.88.22.10
100.64.44.2
```

---

# Requisitos

* Ubuntu 22/24
* Acesso root
* Tailscale conectado
* HAProxy instalado

---

# Observação

Projeto desenvolvido inicialmente para uso interno da Neotech.

