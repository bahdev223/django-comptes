# django-comptes

Moteur réutilisable de comptes financiers pour ERP Django : espèces, banques, Mobile Money, transferts, clôtures et rapprochements.

Le package est conçu pour servir aussi bien une application **mono-entreprise** qu'un SaaS **multi-entreprise**, sans imposer de modèle `Entreprise` au projet hôte.

## Principes

- `Compte` représente une caisse, une banque, un compte Mobile Money ou un autre support financier.
- Les mouvements validés sont protégés contre les modifications et suppressions applicatives directes.
- Les écritures métier passent par des services transactionnels.
- Les transferts verrouillent les comptes avec `select_for_update()`.
- L'idempotence est isolée par entreprise et vérifie le hash du payload.
- Les références externes (`source_system`, `source_type`, `source_id`, `source_reference`) permettent de relier un mouvement à Fournea, Néré, SahelPOS ou un autre ERP.
- Le module reste découplé de `django-comptabilite-ohada` ; l'intégration comptable se fait par événements/signaux.

> La protection fournie est une immutabilité applicative renforcée, pas un registre cryptographiquement inviolable ni une protection contre un administrateur SQL.

## Installation

```bash
pip install -e ".[api]"
```

```python
INSTALLED_APPS = [
    ...
    "comptes",
]
```

```python
urlpatterns = [
    path("api/", include("comptes.urls_api")),
]
```

```bash
python manage.py migrate comptes
```

## Mono-entreprise

Par défaut :

```python
COMPTES = {
    "SCOPING_ENABLED": False,
    "DEFAULT_CURRENCY": "XOF",
}
```

`entreprise_id=""` reste valide. Ce mode convient aux installations locales ou aux ERP qui ne gèrent qu'une organisation.

## Multi-entreprise

En SaaS, activez explicitement le scoping :

```python
COMPTES = {
    "SCOPING_ENABLED": True,
    "SCOPE_RESOLVER": "mon_projet.tenancy.resolve_entreprise_id",
    "DEFAULT_CURRENCY": "XOF",
}
```

Le resolver doit retourner un identifiant non vide :

```python
def resolve_entreprise_id(request):
    return str(request.user.entreprise_id)
```

Quand le scoping est activé, l'absence de tenant provoque un refus d'accès. Il n'existe plus de fallback silencieux vers `entreprise_id=""`.

Avant d'activer le scoping sur une base historique, affectez un `entreprise_id` aux comptes existants. La migration `0008` backfill automatiquement les mouvements, transferts et modes de paiement lorsqu'ils peuvent être dérivés de leurs comptes.

## Idempotence et synchronisation offline

Pour une vente synchronisée depuis Fournea :

```python
mouvement = MouvementCompteService.encaisser(
    compte=caisse,
    montant="15000.00",
    libelle="Vente",
    user=user,
    idempotency_key="fournea:sale:42",
    source_system="fournea",
    source_type="sale",
    source_id="42",
    source_reference="TICKET-0042",
)
```

- même clé + même payload : le même mouvement est retourné ;
- même clé + payload différent : `IdempotencyConflict`.

C'est adapté aux retries d'une file de synchronisation offline-first.

## Providers Mali

Le package fournit un référentiel Mali comprenant les banques, Mobile Money et établissements de paiement utilisés par le moteur d'onboarding.

Les providers globaux sont **en lecture seule dans l'API REST**. Leur mutation passe par les seeds/services d'administration de la plateforme.

Les providers dont l'identité réglementaire ou commerciale doit encore être vérifiée restent `selectable=False`.

## Permissions

Permissions métier principales :

- `comptes.encaisser`
- `comptes.decaisser`
- `comptes.transferer`
- `comptes.annuler`
- `comptes.cloturer`
- `comptes.rapprocher`

Les services critiques vérifient également les permissions lorsqu'un utilisateur est fourni. `user=None` est réservé aux opérations système contrôlées.

## Rapprochement

L'API de rapprochement n'est plus un CRUD générique. Les mutations passent par des actions métier :

- `POST /rapprochements/initialiser/`
- `POST /rapprochements/{id}/pointer/`
- `POST /rapprochements/{id}/depointer/`
- `POST /rapprochements/{id}/ajouter-ligne-releve/`
- `POST /rapprochements/{id}/valider/`

## Tests

```bash
pip install -e ".[api,test]"
pytest -q
```

La CI couvre SQLite et PostgreSQL sur plusieurs versions Python et vérifie également qu'aucune migration n'est manquante.

## Compatibilité

- Python >= 3.10
- Django >= 5.2 et < 6.1
- DRF et django-filter via l'extra `api`

## Licence

MIT
