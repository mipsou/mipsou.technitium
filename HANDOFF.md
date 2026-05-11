# HANDOFF — Ansible Collection `community.technitium`

**Auteur** : Session Claude Code parente — PRA DNS Stack drill 2026-05-11
**Cible** : Claude Code, démarrage projet `community.technitium` from scratch
**Statut** : Repo vide. À structurer + implémenter.
**Repo consommateur de référence** : `D:\workspace\code\mipsou-infra\pra-dns-stack`

---

## 🎯 Objectif

Créer la collection Ansible **`community.technitium`** pour piloter Technitium DNS Server via son API HTTP (token-based auth). Le repo consommateur (`pra-dns-stack`) doit pouvoir remplacer ses `uri` raw + workarounds par des tasks Ansible idempotentes.

Pas de collection community existante pour Technitium — terrain libre. Premier projet du genre. Publier sur Ansible Galaxy + GitHub public. Documenter à Technitium upstream pour qu'ils référencent la collection.

---

## 🔍 Contexte — pourquoi ce projet

Le projet PRA `pra-dns-stack` (chemin local : `D:\workspace\code\mipsou-infra\pra-dns-stack`) déploie Technitium DNS dans un container Podman rootless. Le rôle `roles/technitium/` utilise actuellement le module Ansible `uri` directement pour parler à l'API Technitium. Au cours du drill, **5 bugs/workarounds** ont été découverts qui justifient l'extraction en collection :

### Bugs/workarounds existants — à régression-tester dans la collection

#### 1. `blockingBypassList` = adresses RÉSEAU (CIDR), pas domaines

**Symptôme** : `POST /api/settings/set` avec `blockingBypassList=netflix.com` retourne :
```json
{"status": "error", "errorMessage": "Invalid network address was specified: netflix.com"}
```
mais en **HTTP 200**, donc `uri` ne déclenche pas `failed`.

**Solution** : la whitelist de domaines passe par un fichier `allow-list.txt` monté dans `/etc/dns/config/`. Le module `technitium_setting` devrait :
- Refuser silencieusement de mettre des domaines dans `blockingBypassList`
- Avoir un check `failed_when: json.status != 'ok'` systématique sur tous les calls API

#### 2. `changePassword` requiert `pass` ET `newPass`

**Symptôme** : `POST /api/user/changePassword?token=X&newPass=Y` → erreur "Parameter 'pass' missing".

Les 2 params sont obligatoires : `pass` (current) + `newPass` (new).

**Solution** : module `technitium_user` qui gère la rotation correctement :
```yaml
- community.technitium.user:
    name: admin
    current_password: "{{ vault_current_pwd | default('admin') }}"  # fallback admin
    password: "{{ vault_admin_password }}"
    state: present
```
Idempotent : si login avec `password` réussit déjà → no-op.

#### 3. `blockListUrls` doit être en **champs form répétés**

**Symptôme** : Technitium n'accepte les listes que comme `blockListUrls=url1&blockListUrls=url2&...`. Pas comma-separated, pas newline-separated.

Le module Ansible `uri` avec `body_format: form-urlencoded` + liste Python sérialise mal :
- En folded scalar `>-` : foldé en spaces parasites → API rejette parfois
- En `body_format: json` : token ignoré par Technitium dans body JSON

**Solution** : module `technitium_blocklist` qui :
- Accepte une `list` d'URLs
- Construit le body raw : `'enableBlocking=true&' + '&'.join('blockListUrls=' + urlencode(u) for u in urls)`
- Diff state : compare URLs en mémoire vs déclarées → idempotent
- `changed: false` si déjà à l'état déclaré

#### 4. `blockListLastUpdatedOn` jamais mis à jour de façon fiable

**Symptôme** : Après `forceUpdateBlocklists`, le champ reste `null` même si les blocklists sont effectivement chargées et actives.

**Solution** : ne pas se fier à ce champ pour vérifier le download. Le module `technitium_blocklist` avec `wait_for_active: true` devrait :
- Soit faire un probe DNS sur un domaine connu de la blocklist (ex: `doubleclick.net` → attendre NXDOMAIN)
- Soit poller `blockListNextUpdatedOn` qui lui est settable

#### 5. Fresh container = `admin/admin`, à rotation immédiate

Pas d'env var `DNS_SERVER_ADMIN_PASSWORD` honoré par l'image officielle. Donc bootstrap obligatoire :

1. Tenter login avec password du vault
2. Si fail → fallback `admin/admin`
3. Rotation via `/api/user/changePassword?token=X&pass=admin&newPass=Y`
4. Re-login avec nouveau password

Le module `technitium_session` (auth helper) devrait gérer ça automatiquement avec `bootstrap_password: admin` en fallback.

---

## 📦 Scope minimal v0.1 (priorité PRA)

### Modules

| Module | Priorité | Description |
|--------|----------|-------------|
| `session` | **P0** | auth + token, gère bootstrap admin/admin → rotation auto |
| `setting` | **P0** | get/set settings (DNS, recursion, DNSSEC, etc.) avec diff |
| `blocklist` | **P0** | gestion `blockListUrls` (list state-based), wait_for_active |
| `zone` | **P0** | create/delete primary/secondary/forwarder/stub zones |
| `record` | **P0** | A/AAAA/PTR/MX/TXT/CNAME/NS/SOA add/update/delete |
| `user` | **P1** | gestion users, rotation password idempotente |
| `app` | **P2** | install/configure DNS apps (geo, ad-blocker custom, etc.) |
| `allowed_zone` | **P2** | gestion `/api/allowed/*` (zones jamais bloquées) |
| `blocked_zone` | **P2** | gestion `/api/blocked/*` (zones bloquées manuellement) |

### Module utils

- `module_utils/technitium.py` — client HTTP commun
  - Auth dance avec bootstrap fallback
  - Helpers : `api_get(path)`, `api_post(path, body_dict_or_str)`, `api_form_repeat(path, params)` (pour les listes)
  - Gestion erreurs : `json.status != 'ok'` → fail systématique
  - Cache token entre tasks

### Lookup plugin

- `plugins/lookup/technitium_record.py` — récupère un record DNS depuis Technitium (pour Jinja2)

---

## 🔐 Auth Technitium API

Simple et bien documentée :

1. `GET /api/user/login?user=admin&pass=admin` → `{"token": "...", "status": "ok"}`
2. Token utilisé en query param sur tous les calls suivants : `?token=<token>`
3. Logout (optionnel) : `GET /api/user/logout?token=...`

**Important** : le token est en URL query (pas en header). Si l'URL contient un `&`, attention à l'urlencode du token (généralement c'est juste hex alphanumeric).

Docs API : https://github.com/TechnitiumSoftware/DnsServer/blob/master/APIDOCS.md

---

## 🧪 Tests

### Intégration

Container `technitium/dns-server:latest` lancé localement pour les tests :

```yaml
# tests/integration/setup.yml
- name: Start Technitium test container
  community.docker.docker_container:
    name: technitium-test
    image: technitium/dns-server:latest
    ports:
      - "5380:5380"
    state: started
    wait: true
```

Scénarios :
- Bootstrap admin/admin → rotation password vault
- Login idempotent (re-run avec vault password = OK direct)
- Create zone primary `test.local` → idempotent
- Add A record → idempotent
- Set blocklist URLs (list de 6) → vérifier API a stocké les 6
- Wait for blocklist active (probe `doubleclick.net` → NXDOMAIN)
- Update setting (DNSSEC enable) → diff
- Delete record → re-run delete = changed=false

### Régression PRA

Les 5 bugs ci-dessus → fixés et testés. Si l'API Technitium change demain, les tests doivent le détecter.

### Unit

- Mock HTTP, tester le bootstrap flow (vault fail → admin/admin → rotate → retry vault)
- Tester la sérialisation list → repeated form fields

---

## 📂 Structure repo proposée

```
community.technitium/
├── README.md
├── LICENSE              # GPL-3.0-or-later
├── galaxy.yml           # namespace: community, name: technitium, version: 0.1.0
├── meta/
│   └── runtime.yml
├── plugins/
│   ├── modules/
│   │   ├── session.py
│   │   ├── setting.py
│   │   ├── blocklist.py
│   │   ├── zone.py
│   │   ├── record.py
│   │   └── user.py
│   ├── module_utils/
│   │   └── technitium.py
│   └── lookup/
│       └── technitium_record.py
├── tests/
│   ├── integration/
│   │   ├── setup.yml
│   │   ├── teardown.yml
│   │   └── targets/
│   │       ├── blocklist/
│   │       ├── zone/
│   │       ├── record/
│   │       └── user_rotation/
│   └── unit/
├── docs/
│   ├── getting_started.md
│   ├── bootstrap_admin.md   # explique le pattern fresh-container
│   └── api_quirks.md         # liste les 5 bugs + comportements API surprenants
└── .gitlab-ci.yml
```

---

## 🚀 Roadmap

### v0.1.0 (PRA-driven)

- ✅ Modules P0 : `session`, `setting`, `blocklist`, `zone`, `record`
- ✅ Module utils auth
- ✅ Bootstrap admin/admin → rotation auto dans `session`
- ✅ Integration tests avec container Technitium réel (CI GitLab + podman)
- ✅ README + docs `bootstrap_admin.md` + `api_quirks.md`

### v0.2.0

- Module `user` (multi-users)
- Module `allowed_zone`, `blocked_zone`
- Lookup `technitium_record`

### v0.3.0+

- Module `app` (Technitium DNS Apps)
- Module `dns_settings` (DoH/DoT/DoQ config)
- Inventory plugin pour générer inventory depuis les zones

---

## 💡 Exemples cible

### Bootstrap propre

```yaml
- community.technitium.session:
    host: 192.168.100.23
    port: 5380
    user: admin
    password: "{{ vault_technitium_admin_password }}"
    bootstrap_password: admin        # fallback fresh container
    rotate_if_bootstrap: true        # change le password si bootstrap déclenché
  register: tech
```

### Blocklist

```yaml
- community.technitium.blocklist:
    session: "{{ tech }}"
    urls: "{{ lookup('file', 'dnsbl_sources.txt').splitlines() | select('match', '^https?://') | list }}"
    enabled: true
    wait_for_active:
      probe_domain: doubleclick.net
      expect_rcode: NXDOMAIN
      timeout: 300
```

### Zone + records

```yaml
- community.technitium.zone:
    session: "{{ tech }}"
    name: chp-domain.eu
    type: primary
    state: present

- community.technitium.record:
    session: "{{ tech }}"
    zone: chp-domain.eu
    name: ns1.chp-domain.eu
    type: A
    value: 192.168.100.23
    ttl: 3600
    state: present
```

Comparer aux ~15 tasks `uri` raw actuelles dans `pra-dns-stack/ansible/roles/technitium/tasks/zones.yml`.

---

## 🔗 Liens

- **API docs Technitium** : https://github.com/TechnitiumSoftware/DnsServer/blob/master/APIDOCS.md
- **Image Docker** : `docker.io/technitium/dns-server:latest`
- **Galaxy publish** : https://galaxy.ansible.com/docs/contributing/creating_collections.html
- **Repo PRA consommateur** : `D:\workspace\code\mipsou-infra\pra-dns-stack\ansible\roles\technitium\`
- **Rôle Ansible actuel** : sert de référence pour migration (URLs, params API testés)

---

## 💡 Conseils pour démarrer

1. **Bootstrap** : `ansible-galaxy collection init community.technitium`
2. **Premier module** : `session.py` (toute la collection en dépend)
3. **Test rapide** : `podman run -d -p 5380:5380 technitium/dns-server:latest`, puis dev contre `http://localhost:5380`
4. **Lire les workarounds PRA d'abord** : `cat D:\workspace\code\mipsou-infra\pra-dns-stack\ansible\roles\technitium\tasks\*.yml` — comprendre les patterns douloureux avant de coder leur équivalent propre
5. **Documenter chaque quirk** : `docs/api_quirks.md` doit être exhaustif, c'est la valeur ajoutée de la collection face à `uri` raw

Quand prêt : `ansible-galaxy collection build && ansible-galaxy collection publish community-technitium-0.1.0.tar.gz`

---

## ❓ Questions ouvertes pour ta session

- Faut-il un `session` persisté entre tasks/plays via fact (`set_fact: _tech_token`) ou via lookup `community.technitium.token` ?
- Le module `blocklist` doit-il merger les URLs existantes avec les nouvelles, ou remplacer (state-based) ? Recommandation : remplacer, state-based.
- Faut-il supporter Technitium en mode cluster (multi-instances) dès v0.1, ou plus tard ?
- Comment gérer l'image Technitium en CI (puller à chaque run = lent, cacher dans registry GitLab = plus rapide) ?

À toi de juger selon le scope v0.1.0. Minimum viable : modules P0 + auth bootstrap + 1 integration test.

Bon code 🚀
