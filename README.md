# django-comptes

**Module universel de gestion des comptes financiers** pour Django.

Gère tous les types de comptes (Espèces, Banque, Mobile Money, Carte, Portefeuille numérique) avec historique infalsifiable, transfers inter-comptes, clotures journalières et rapprochements bancaires.

Conçu comme un **module ERP réutilisable** : aucune dépendance vers des modèles métier spécifiques (client, fournisseur, école, hôpital). Utilise un système de signaux pour notifier les autres modules sans couplage.

## Fonctionnalités

- **Comptes universels** : Espèces, Banque, Mobile Money, Carte, Portefeuille numérique
- **Mouvements typés** : Encaissement, Décaissement, Transfert, Ajustement, Ouverture, Clôture, Annulation
- **Suivi d'état** : Brouillon, Validé, Annulé, Rapproché
- **Transferts atomiques** entre comptes
- **Clôture journalière/périodique** avec calcul des écarts
- **Rapprochement bancaire** complet
- **Historique d'audit** de chaque compte
- **Multi-devise** prêt (taux de change, devise de référence)
- **Permissions fines** par opération
- **API REST** complète (DRF)
- **Signal-based architecture** — découplé du module comptabilité

## Installation

```bash
pip install django-comptes
```

ou depuis le dépôt :

```bash
pip install git+https://github.com/bah-dev/django-comptes.git
```

## Configuration rapide

1. Ajouter `'comptes'` à `INSTALLED_APPS` :

```python
INSTALLED_APPS = [
    ...
    'comptes',
]
```

2. Inclure les URLs :

```python
urlpatterns = [
    ...
    path('comptes/', include('comptes.urls')),
    path('api/comptes/', include('comptes.urls_api')),
]
```

3. Lancer les migrations :

```bash
python manage.py migrate comptes
```

## Configuration avancée

```python
# settings.py
COMPTES = {
    'DEFAULT_CURRENCY': 'XOF',
    'ALLOW_OVERDRAFT': False,
    'AUTO_CREATE_ACCOUNTING_ENTRIES': True,
}
```

## Architecture

```
comptes/
├── models/
│   ├── compte.py              # Compte financier
│   ├── mouvement_compte.py    # Mouvements typés
│   ├── transfert_compte.py    # Transferts inter-comptes
│   ├── journal_compte.py      # Journaux quotidiens
│   ├── rapprochement.py       # Rapprochement bancaire
│   ├── cloture.py             # Clôtures périodiques
│   ├── historique_compte.py   # Audit trail
│   ├── favori.py              # Comptes favoris/défaut
│   └── managers.py            # QuerySet personnalisé
├── services/
│   ├── compte_service.py
│   ├── mouvement_service.py
│   ├── transfert_service.py
│   ├── journal_service.py
│   ├── cloture_service.py
│   └── rapprochement_service.py
├── signals/                   # Signaux découplés
├── api/                       # DRF ViewSets
├── selectors.py               # Requêtes de lecture
├── permissions.py             # Permissions fines
└── defaults.py                # Configuration
```

## Utilisation

### Créer un compte

```python
from comptes.models import Compte
from comptes.services import CompteService

compte = CompteService.creer(
    code="CP-001",
    nom="Caisse Principale",
    type_compte="ESPECES",
    solde_initial=Decimal("100000.00"),
    devise="XOF",
)
```

### Encaisser / Décaisser

```python
from comptes.services import MouvementCompteService

# Encaissement
MouvementCompteService.encaisser(
    compte=compte, montant=50000,
    libelle="Vente du jour", user=request.user,
)

# Décaissement (avec contrôle du solde)
MouvementCompteService.decaisser(
    compte=compte, montant=15000,
    libelle="Achat fournitures", user=request.user,
)
```

### Transférer entre comptes

```python
from comptes.services import TransfertCompteService

TransfertCompteService.transferer(
    source=compte_caisse,
    destination=compte_banque,
    montant=30000,
    user=request.user,
    notes="Dépôt banque hebdomadaire",
)
```

### Clôture journalière

```python
from comptes.services import ClotureCompteService

cloture = ClotureCompteService.cloturer(
    compte=compte,
    solde_reel=Decimal("135000.00"),
    user=request.user,
)
```

## Signaux disponibles

Le module émet des signaux Django standards que d'autres apps peuvent écouter :

```python
from comptes.signals.mouvement import (
    mouvement_valide,
    mouvement_annule,
    transfert_effectue,
    compte_cloture,
    rapprochement_valide,
)
```

## Licence

MIT
