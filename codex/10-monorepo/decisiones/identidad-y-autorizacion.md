---
id: null
type: decision
project: monorepo
parent: "[[moc-monorepo]]"
status: Propuesto
alcance: "Todo el monorepo cosmos: pulsar (primer proyecto) y todo lo que venga"
created: 2026-06-30
updated: 2026-06-30
relacionado: []
tags: [seguridad, arquitectura]
---

# Identidad y autorización — arquitectura de la suite

↑ Pertenece a: [Monorepo](../moc-monorepo.md)

| | |
| --- | --- |
| **Tipo** | Decisión de arquitectura transversal (suite-wide). Candidata a `COSMOS-ADR-0001` cuando cierren las decisiones abiertas. |
| **Alcance** | Todo el monorepo `cosmos`: `pulsar` (primer proyecto) y todo lo que venga (torre de control de proveedores, backends NestJS, frontends Next.js, apps internas). |
| **Objetivo** | Un **servicio central de autenticación + autorización**, language-agnostic, reutilizable desde cualquier app (Python, Next.js, NestJS, futuros). |
| **Estado** | **Dirección decidida; faltan dos decisiones (build-vs-buy del IdP y confirmación del motor de autz).** Ver §10. |
| **Motivación raíz** | Una orden de compra duplicada costó **>1M MXN** por falta de trazabilidad de "quién hizo qué". La identidad + autorización + auditoría es el cimiento que lo previene. |

> **Cómo leer este documento.** Cada afirmación lleva una etiqueta de
> confianza:
> - **[V]** Verificado: de fuente primaria (RFC/spec) que sobrevivió
>   verificación adversarial (investigación multi-fuente, votación 3-0).
>   Fuentes en §11.
> - **[E]** Establecido: consenso de industria / práctica estándar.
> - **[C]** Criterio: juicio arquitectónico propio aterrizado a nuestro caso.

---

## 1. Contexto y problema

`cosmos` no es un proyecto, es una **suite**: muchos proyectos y
**muchísimos tipos de usuario** coexistiendo en el mismo ambiente — cadena de
suministro, compras, finanzas de sucursales, proveedores, gerentes, y más por
venir. Dos hechos lo definen:

1. **Web expuesto a usuarios poco técnicos.** El login es la primera capa de
   seguridad y está bajo amenaza real de **phishing, contraseñas débiles y
   brute-force**. No podemos depender de la buena conducta del usuario.
2. **Autorización combinatoria.** Un proveedor no tiene nada que hacer en la
   API de pulsar; un finanzas de sucursal Norte no debe ver datos de la Sur.
   Resolver esto con roles ad-hoc por cada combinación (proyecto × tipo ×
   sucursal × operación) **explota** y es imposible de auditar — exactamente
   la trampa que hay que evitar.

La lección del incidente de la OC duplicada: **eficiencia sin trazabilidad
mata el negocio.** Por eso authn/authz se diseñan como cimiento, con la
**auditoría como requisito de primera clase**, antes de construir dominios
que muten estado de negocio.

## 2. Principios

- **P1 — Servicio central, no por-proyecto.** Una sola fuente de verdad de
  identidad y de "quién puede hacer qué" para toda la suite. Cada proyecto
  *pregunta*; no reimplementa lógica de permisos. [C]
- **P2 — Language-agnostic por contrato.** El servicio se consume por una
  **API estándar sobre HTTP**; Python (FastAPI), Next.js, NestJS y cualquier
  lenguaje futuro hablan el mismo contrato. SDKs delgados por lenguaje, una
  sola política central. [C]
- **P3 — Default-deny.** Sin permiso explícito, se niega. [E]
- **P4 — Phishing-resistant por diseño**, no por capacitación del usuario. [C]
- **P5 — Toda decisión se audita** (permitir *y* negar), y todo cambio de
  asignación de permisos también. El audit trail es no repudiable. [C]
- **P6 — Capas separadas y combinables.** Identidad de usuario, identidad de
  carga (servicio-a-servicio), modelo de permisos, contrato de decisión y
  auditoría son capas distintas; se eligen y evolucionan por separado. [V]

## 3. Autenticación (el login)

**Decisión: passkeys (WebAuthn/FIDO2) como método primario, sobre OAuth 2.1 +
OIDC.**

- **Passkey primero.** Es el único mecanismo que neutraliza nuestras tres
  amenazas a la vez: no hay contraseña que adivinar (brute-force muere) y la
  credencial está atada criptográficamente al dominio real (phishing muere
  aunque el usuario caiga en un sitio falso). Es *phishing-resistant* por
  diseño. [E] Para usuarios poco técnicos es además **más simple**
  (huella/cara, nada que recordar ni teclear) con passkeys sincronizadas. [C]
- **Recuperación y fallback.** Magic link / OTP por correo son passwordless
  **pero NO son phishing-resistant**: se usan solo como recuperación o
  fallback de baja confianza, **nunca** como puerta principal de usuarios de
  alto privilegio. [C]
- **Alto privilegio (compras, finanzas, gerencia): factor phishing-resistant
  obligatorio**, sin opción de bajar a OTP. [C]
- **Protocolo: OAuth 2.1 + OpenID Connect**, flujo Authorization Code **+
  PKCE obligatorio** para todos los clientes (SPAs Next.js, apps internas,
  portal B2B de proveedores). Implicit grant y Password grant (ROPC)
  **eliminados**. [V]
  - Madurez: OAuth 2.1 aún es Internet-Draft (RFC final ~dic-2026), pero su
    sustancia de seguridad ya está ratificada en **RFC 9700 (BCP, ene-2025)**
    — *esa* es la referencia normativa citable. [V]

## 4. Seguridad de token

**Decisión: tokens sender-constrained.** Para mitigar robo/exfiltración de
token, RFC 9700 recomienda atar el token al cliente (SHOULD): [V]

- **DPoP (RFC 9449)** para clientes públicos / SPA / portal B2B (sin PKI de
  cliente).
- **mTLS (RFC 8705)** para servicio-a-servicio con certificados gestionados
  (encaja con SPIFFE, §8).

Un token robado queda inservible sin la llave privada del cliente. Detalle
fino de formato (JWT vs opaco, JWS/JWE, rotación de refresh tokens, PASETO)
queda **pendiente** (§10).

## 5. Autorización — el modelo de 3 + 1 dimensiones

El acceso se evalúa en **cascada, fail-fast** (de grueso a fino). Las tres
primeras dimensiones responden *"¿qué tipo de operación?"*; la cuarta,
*"¿sobre cuáles datos?"*.

| # | Dimensión | Pregunta | Ejemplo de denegación |
| - | --------- | -------- | --------------------- |
| 1 | **Proyecto** | ¿El usuario puede operar en este proyecto? | Un proveedor consultando la API de `pulsar` → **deny** |
| 2 | **Módulo / recurso** | ¿Tiene acceso a este módulo? | Sin acceso a `cadena_suministro` → **deny** |
| 3 | **Acción (CRUD)** | ¿Puede hacer *esta* operación? | Tiene `read` pero intenta `update` → **deny** |
| 4 | **Scope de datos** | ¿Sobre *este* registro en concreto? | Finanzas de sucursal Norte editando una OC de la Sur → **deny** |

La **4ª dimensión** (scope de datos / tenencia: por sucursal, por proveedor,
por región) es ortogonal a las tres primeras y es donde el RBAC puro se
rompe y donde vive el radio de daño del incidente de >1M MXN. **No estaba en
el planteamiento inicial; se añade explícitamente.** [C]

### Vocabulario (evita la explosión de roles)

La regla de oro: **nunca se asignan permisos sueltos a usuarios; se asignan
roles.** [E]

| Concepto | Qué es | Ejemplo |
| -------- | ------ | ------- |
| **Permiso** (atómico) | El triple `proyecto:módulo:acción` que declara cada endpoint | `pulsar:compras:update` |
| **Rol** (bundle) | Paquete reutilizable de permisos, mapeado a una función de trabajo | `comprador`, `gerente_finanzas`, `proveedor` |
| **Asignación** | Qué rol tiene un usuario **y en qué scope** | "Ana = `gerente_finanzas` en *sucursal Norte*" |
| **Scope** | La frontera de datos de una asignación (4ª dimensión) | `sucursal:norte`, `proveedor:X` |

### Ejemplo de decisión completa (las 4 dimensiones)

> Ana quiere **editar la OC #123**.
> 1. Proyecto `pulsar` → ✓ (tiene acceso)
> 2. Módulo `pulsar:compras` → ✓
> 3. Acción `update` → ✓ (rol `comprador`)
> 4. Scope: la OC #123 pertenece a *sucursal Norte*, donde Ana opera → ✓ →
>    **ALLOW** (si la #123 fuera de *sucursal Sur* → **DENY**, mismo rol,
>    distinto scope)

## 6. Cómo lo resuelve la industria: servicio central híbrido (RBAC + ReBAC)

**Decisión: un PDP (Policy Decision Point) central para toda la suite**, con
dos mecanismos combinados:

- **RBAC grueso** para las dimensiones 1–3 (proyecto/módulo/CRUD): gatea
  rutas y endpoints. Rápido, simple, auditable. [E]
- **ReBAC** (modelo **Zanzibar** de Google) para la dimensión 4 (scope de
  datos): se modela `Ana —opera_en→ sucursal_Norte` y `proveedor_X
  —dueño_de→ OC_123` como **relaciones**, no como roles. ReBAC es
  **superset de RBAC** y cubre ABAC cuando los atributos se expresan como
  relaciones, así que ambos mecanismos viven en **un solo motor**: se empieza
  con forma RBAC y se crece al scope fino **sin re-arquitectar**. [V]

**Contrato language-agnostic (P2):** el PEP (Policy Enforcement Point,
embebido en cada app: FastAPI, Next.js, NestJS) le pregunta al PDP *"¿puede
el sujeto S hacer la acción A sobre el recurso R en el contexto C?"* vía el
estándar **OpenID AuthZEN Authorization API 1.0** (Final ene-2026). [V] Esto
desacopla la app del motor: la app no contiene lógica de permisos, solo el
punto que pregunta; el motor detrás es intercambiable.

**Por qué escala a la suite** [C]:
- **Nuevo proyecto** = nuevo *namespace* de permisos en el mismo PDP, no un
  auth nuevo.
- **Nuevo tipo de usuario** = un rol nuevo (bundle), cero código.
- **Nuevo endpoint** = declara su permiso `proyecto:módulo:acción`.
- **Una sola fuente de verdad** que responde *"¿quién puede hacer qué?"* —
  que es exactamente la auditabilidad que faltó en el incidente.

> Nota de madurez: AuthZEN es estándar **ratificado pero muy reciente**
> (ecosistema incipiente). Se adopta como **contrato** (forma de la API), no
> como dependencia crítica todavía; si su ecosistema no madura, el contrato
> se sirve igual sobre el motor elegido. [V]

## 7. El servicio orquestador (el proyecto central de auth)

El servicio central (§2, P1) es un **proyecto de primera clase del
monorepo**, al mismo nivel que `pulsar` (vive en `projects/`, con su propio
stack). Es el **control plane de auth de la suite**: la fuente única de
verdad de identidad y permisos, y el que orquesta IdP + PDP, gestiona
usuarios/roles/scopes y agrega la auditoría.

> Nombre clave propuesto: **`polaris`** (la estrella guía / fuente única de
> verdad), en línea con el tema del monorepo. Pendiente de confirmar. [C]

### Tecnología: Node / NestJS [C]

El orquestador se implementa en **Node + NestJS**. No porque "corra" el IdP o
el PDP —esos son productos maduros desplegados aparte (§3, §6), en su propio
lenguaje (Go/Java)— sino porque es donde vive **nuestra** lógica alrededor de
ellos. Razones:

- **Madurez de librerías para estos estándares en concreto:** WebAuthn/passkeys
  (SimpleWebAuthn), clientes OIDC y los SDKs de OpenFGA/AuthZEN son TS-first y
  los más maduros del ecosistema.
- **Coherencia de stack:** NestJS ya está previsto para los backends de
  integración, así que no se añade un lenguaje nuevo a la suite.

> Importante: **"orquestar" ≠ "construir".** El orquestador *integra* IdP y
> PDP; **no** reimplementa identidad ni el motor de decisión. Escribir un IdP
> propio sería el anti-patrón "rápido sin cimientos" que motivó este
> documento (§1). "Self-host" (correr un producto maduro en nuestra infra)
> **no** es "build".

### Dos planos: no confundir gestión con decisión [C]

| Plano | Qué hace | Dónde vive | ¿En cada request? |
| ----- | -------- | ---------- | ----------------- |
| **Gestión** (management) | alta de usuarios, asignación de roles/scopes (modelo 3+1), agregación de auditoría, panel admin, SDK uniforme | **el orquestador (Node)** | No |
| **Decisión** (per-request) | *"¿puede el sujeto S la acción A sobre el recurso R?"* | **PEP de cada app → PDP directo** (AuthZEN) | Sí |

Regla crítica: **el chequeo per-request NO rebota por el orquestador.** El
PEP consulta al PDP (OpenFGA) **directo**, por latencia y para no convertir
al orquestador en un **único punto de falla** de toda la suite. El
orquestador es el *cerebro de administración*; el PEP→PDP es el *reflejo
rápido* de cada llamada.

### Diagrama

```
[IdP: Zitadel/Keycloak]      [PDP: OpenFGA]        ← productos maduros desplegados (Go/Java)
        ▲                          ▲                  NO los escribimos
        │ orquesta/admin           │ modelo + asignaciones
   ┌────┴──────────────────────────┴─────┐
   │   Orquestador  ·  Node/NestJS        │         ← control plane (proyecto del monorepo)
   │   usuarios · roles/scopes · audit    │           plano de gestión
   └──────────────────────────────────────┘
                                    ▲ (decisión per-request, DIRECTO al PDP)
      [PEP pulsar/Py]  [PEP Next/TS]  [PEP Nest/TS]   ← en cada app, en su lenguaje
```

## 8. Identidad servicio-a-servicio y auditoría

- **Servicio-a-servicio (workload identity): SPIFFE/SPIRE.** Cuando los
  backends se hablen (FastAPI ↔ NestJS ↔ …), identidad de carga con SVIDs de
  vida corta (X.509 para mTLS, y JWT), rotación automática, atestación
  nodo+workload, **sin "secret zero"**. SPIFFE **no** resuelve autorización
  ni identidad humana: es complementario a OAuth (incluso puede bootstrapear
  el cliente OAuth). [V]
- **Auditoría (requisito de primera clase): OpenID Shared Signals** (SSF +
  CAEP + RISC, Final sep-2025) sobre **Security Event Tokens firmados (SET,
  RFC 8417)**. Da eventos de seguridad **no repudiables** ("quién, qué,
  cuándo, resultado") y, vía **CAEP**, **revocación / evaluación continua de
  sesión** casi en tiempo real — la capacidad de *detectar y cortar en
  caliente* que faltó en el incidente. [V] Cada decisión del PDP (allow y
  deny) y cada cambio de asignación alimentan este trail.

## 9. Resumen de decisiones tomadas

| Capa | Decisión | Madurez |
| ---- | -------- | ------- |
| Autenticación | Passkeys (WebAuthn/FIDO2) primero, sobre OAuth 2.1 + OIDC + PKCE | Maduro |
| Token | Sender-constrained (DPoP público / mTLS S2S) | Maduro |
| Modelo de autz | Híbrido: RBAC grueso (dims 1–3) + ReBAC/Zanzibar (dim 4 scope) | Maduro |
| Servicio de autz | **PDP central** para toda la suite, default-deny | — |
| Orquestador | Proyecto central en **Node/NestJS** (control plane); fuera del camino per-request | — |
| Contrato | OpenID AuthZEN Authorization API (PEP↔PDP), language-agnostic | Emergente (ratificado) |
| Servicio-a-servicio | SPIFFE/SPIRE | Maduro |
| Auditoría | OpenID Shared Signals (SSF/CAEP/RISC) sobre SET | Maduro |

## 10. Pendiente por decidir

1. **Build vs Buy del IdP** *(la más urgente; sin evidencia aún)*. ¿Self-hosted
   (Keycloak / Ory / Zitadel / Authentik) o SaaS (Auth0 / WorkOS / Clerk /
   Stytch)? Criterios: passkeys, B2B multi-tenant para proveedores, audit log
   inmutable exportable, soporte Shared Signals, encaje con equipo de 5+ devs.
2. **Motor de autz concreto** detrás de AuthZEN: **OpenFGA** (ReBAC/Zanzibar,
   CNCF) vs AWS Cedar vs OPA/Rego. Confirmar XACML como legacy a descartar.
   Evaluar rendimiento del check por-request e integración con
   FastAPI/NestJS.
3. **Detalle de token/sesión**: JWT vs opaco, JWS vs JWE, PASETO, rotación de
   refresh tokens.
4. **SAML 2.0**: ¿necesario para federar con IdPs de proveedores grandes, o
   basta OIDC?
5. **Cumplimiento México (LFPDPPP** y reforma 2025 / autoridad sucesora del
   INAI**)**: retención, residencia y trazabilidad de logs de acceso a datos
   personales; condiciona self-hosted vs SaaS y dónde vive el audit trail.

## 11. Fuentes (primarias verificadas)

- OAuth 2.1 — draft-ietf-oauth-v2-1: https://datatracker.ietf.org/doc/draft-ietf-oauth-v2-1/ · https://oauth.net/2.1/
- RFC 9700 (BCP OAuth 2.0 Security, ene-2025): https://datatracker.ietf.org/doc/rfc9700/
- DPoP — RFC 9449 · mTLS — RFC 8705 (sender-constrained tokens, vía RFC 9700 §2.2.1)
- OpenFGA / Zanzibar: https://openfga.dev/docs/authorization-concepts · Paper USENIX ATC '19: https://www.usenix.org/system/files/atc19-pang.pdf
- OpenID AuthZEN Authorization API 1.0 (Final): https://openid.net/authorization-api-1-0-final-specification-approved/ · https://openid.net/specs/authorization-api-1_0.html
- SPIFFE/SPIRE: https://spiffe.io/docs/latest/spire-about/spire-concepts/ · SPIFFE↔OAuth (IETF 116): https://datatracker.ietf.org/meeting/116/materials/slides-116-oauth-sessb-oauth-and-spiffe-00.pdf
- OpenID Shared Signals (SSF/CAEP/RISC, Final sep-2025): https://openid.net/three-shared-signals-final-specifications-approved/ · SSF: https://openid.net/specs/openid-sharedsignals-framework-1_0-final.html · CAEP: https://openid.net/specs/openid-caep-1_0-final.html · SET — RFC 8417: https://www.rfc-editor.org/rfc/rfc8417.html

---

*Investigación de respaldo: harness multi-fuente con verificación adversarial
(24 fuentes, 25 claims verificados 3-0, 0 refutados). El núcleo (OAuth
2.1/RFC 9700, ReBAC/Zanzibar, AuthZEN, SPIFFE, Shared Signals) es de fuente
primaria verificada; los puntos de §10 quedaron fuera del alcance verificado
y se tratan como no investigados.*
