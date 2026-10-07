# Mobile Money : audit des parcours et frontière PI-SPI

Audit effectué le **7 octobre 2026** sur `bahdev223/django-comptes`, branche
`main`, commit `1682ecc081e46ab7c6787b7eca6b2aea68ec9618`.
La branche `fix/tenant-security-data-integrity` est déjà un ancêtre de cette
version et aucune PR ouverte n'a été trouvée lors de la vérification.
Le périmètre est le package et ses points d'entrée ; les applications hôtes et
leurs éventuels récepteurs de signaux ne sont pas audités ici.

## Décision

**Le package enregistre des flux internes. Il n'exécute, ne route et ne tarifie
aucun transfert Mobile Money externe.** L'Avis n°0019 ne justifie donc pas
l'ajout d'un routeur, d'un barème, d'un compteur quotidien ou d'une migration
PI-SPI dans ce moteur tel qu'il existe au commit audité.

Cette conclusion vient de la lecture des services, modèles, serializers,
vues REST et HTML, signaux, seeds et dépendances, et non du seul README.
Elle n'atteste pas la conformité d'une application hôte qui exécuterait des
paiements par un autre module.

## Texte de référence et dates

Sources officielles consultées :

- [Avis BCEAO n°0019, page de publication](https://www.bceao.int/fr/reglementations/avis-ndeg0019-relatif-aux-transactions-de-monnaie-electronique-entre-personnes).
- [Avis signé, PDF](https://www.bceao.int/sites/default/files/2026-10/AVIS%20N%C2%B0%200019%20%20DU%202%20OCTOBRE%202026%20%281%29.pdf).
- [Communiqué BCEAO détaillant les nouvelles conditions](https://ns2.bceao.int/index.php/fr/communique-presse/transactions-de-monnaie-electronique-entre-personnes-physiques-par-0).

L'avis concerne les transferts de monnaie électronique entre personnes
physiques définis par la Convention de participation à PI-SPI, au niveau national
et dans l'UEMOA, entre toutes les catégories de participants. Il s'adresse aux
établissements concernés, notamment banques,
institutions de microfinance, établissements de monnaie électronique et de
paiement. Un encaissement commercial enregistré dans un ERP ne doit pas être
automatiquement assimilé à un transfert entre personnes physiques.

| Date d'effet | Disposition à traiter par l'acteur qui exécute ou tarifie les opérations concernées |
| --- | --- |
| 2 novembre 2026 | Les transactions interopérables de monnaie électronique dans l'UEMOA passent obligatoirement par PI-SPI. |
| 2 novembre 2026 | À l'émission nationale, gratuité jusqu'à 8 000 FCFA cumulés quotidiennement par utilisateur et participant, sans limite de nombre d'opérations ; au-delà, frais possibles de 0 à 0,8 % sur le montant hors taxes du transfert. |
| 2 novembre 2026 | Réception gratuite, sans limite de montant ni de nombre d'opérations, dans le périmètre applicable. |
| 1er juin 2027 | Les conditions des transferts entre pays de l'UEMOA deviennent identiques aux conditions nationales. |

Le plafond de 0,8 % n'est pas un tarif obligatoire. La date de publication ne
doit pas être confondue avec les dates d'effet. Les règles intra-UEMOA ne
doivent pas être anticipées avant leur date applicable. Le point 3 distingue
le cumul quotidien donnant droit à la gratuité et le montant du transfert pour
le tarif au-dessus de 8 000 FCFA : il ne faut pas en déduire sans règles
opérationnelles un calcul sur la seule fraction dépassant le seuil.

## Parcours réels

Les chemins HTTP ci-dessous sont relatifs au préfixe choisi par le projet hôte.
Par exemple, inclure `comptes.urls_api` sous `/api/` donne
`/api/transferts/transferer/`.

| Entrée | Chemin de code | Effet réel |
| --- | --- | --- |
| REST `POST /transferts/transferer/` | `comptes/urls_api.py` → `TransfertCompteViewSet.transferer` dans `comptes/api/views.py` → `TransfertInputSerializer` → `TransfertCompteService.transferer` | Résout deux comptes internes, applique le scoping si activé, enregistre le transfert et deux mouvements. |
| HTML `POST /transferts/` | `comptes/urls.py` → `transfert_effectuer` dans `comptes/views/transferts.py` → même service | Saisie manuelle du transfert interne ; trace `django-html` / `manual-transfer`. |
| Appel Python par un ERP | `TransfertCompteService.transferer` dans `comptes/services/transfert_service.py` | Même transaction interne, indépendamment du type ou du fournisseur des comptes. |
| REST `POST /mouvements/encaisser/` et `/mouvements/decaisser/` | `MouvementCompteViewSet` → `MouvementCompteService.encaisser` / `decaisser` → `_creer` | Enregistre le montant fourni sur un seul compte. Ne collecte ni ne verse de monnaie électronique. |
| HTML `POST /mouvements/encaisser/` et `/mouvements/decaisser/` | `comptes/views/mouvements.py` → mêmes services | Saisie manuelle d'une entrée ou sortie ; trace `django-html` / `manual`. |
| Ajustement et annulation | `MouvementCompteService.ajuster` / `annuler` dans `comptes/services/mouvement_service.py` | Ajustement du registre ou contre-mouvement local. Une annulation ne déclenche aucun remboursement externe. |
| Choix d'un provider | `FinancialProviderService.synchroniser_mali` et `FinancialOnboardingService.configurer_comptes` dans `comptes/services/financial_provider_service.py` | Crée ou actualise le référentiel, les comptes et les modes de paiement locaux. N'ouvre aucun portefeuille chez l'opérateur. |
| Rapprochement | Actions de `RapprochementBancaireViewSet`, vues dans `comptes/views/rapprochement.py` → `RapprochementService` | Compare les écritures sélectionnées avec les données de relevé fournies et permet leur pointage. Aucun relevé PI-SPI n'est téléchargé. |

### Le transfert inter-comptes, étape par étape

Dans `TransfertCompteService.transferer` :

1. Vérification de la permission `comptes.transferer`, de deux comptes distincts,
   d'une même entreprise et d'un montant positif.
2. Construction du hash du payload et recherche d'une éventuelle clé
   d'idempotence dans cette entreprise.
3. Verrouillage des deux comptes dans l'ordre de leur identifiant ; vérification
   de leur activité et du disponible local de la source.
4. Création de `TransfertCompte` avec une référence interne `TRF-…` et les
   éventuelles références externes fournies par l'appelant.
5. Deux appels à `MouvementCompteService.transfert` : `SORTIE` sur la source,
   `ENTREE` sur la destination, chacun pour le même `montant`. `_creer` persiste
   les mouvements puis `_mettre_a_jour_solde` actualise les soldes locaux.
6. Les signaux sont programmés avec `transaction.on_commit` si les événements
   sont activés. Ils annoncent des écritures internes déjà enregistrées.

Le service ne consulte ni `Compte.provider`, ni un numéro de téléphone, ni un
participant PI-SPI. Aucun tarif n'est appliqué, même si les deux comptes ont des
providers Mobile Money différents. Les montants de 7 999, 8 000 et 8 001 FCFA
suivent les mêmes contrôles de registre, sans compteur quotidien réglementaire.

`TransfertCompte.date` est la date de création locale (`auto_now_add`), pas la
date d'exécution chez un participant. `valide_par` et `user` désignent l'acteur
applicatif ; ils ne constituent pas l'identité réglementaire de l'émetteur.
`entreprise_id` isole les écritures d'un tenant ; il ne désigne pas le participant
utilisé pour le cumul tarifaire.

### Absence d'exécution et de tarification dans le package

- `TransfertInputSerializer` accepte des comptes, un montant, des notes, une clé
  d'idempotence et des références de provenance. Il n'accepte aucun ordre
  opérateur, devis tarifaire, rail, participant ou frais de réception.
- `TransfertCompte` ne possède ni frais, ni taux, ni statut d'exécution externe.
  La référence `TRF-…` n'est pas une référence de règlement PI-SPI.
- `FinancialProvider` contient une identité commerciale, une famille, un pays,
  un logo et des métadonnées génériques. Ces métadonnées ne sont consommées par
  aucun calcul de tarif ou choix de rail dans les parcours inspectés.
- Les services et vues Python ne contiennent aucun client réseau de paiement,
  connecteur opérateur, webhook ou routeur. Les dépendances déclarées sont
  celles de Django et de l'API, sans SDK de paiement. Le script de récupération
  des logos concerne uniquement les assets de marque.
- `comptes/signals/mouvement.py` déclare les événements ; le package n'installe
  aucun handler qui exécute un paiement. Un handler ajouté par le projet hôte
  doit être audité séparément.

## Contrat avec l'application ou le connecteur externe

### Enregistrer une opération confirmée

L'application hôte obtient la confirmation du participant ou de son connecteur,
vérifie le périmètre de l'opération et transmet les montants constatés au registre.

- Deux comptes appartenant à la même entreprise et tenus dans ce registre :
  utiliser `TransfertCompteService.transferer` pour le principal.
- Un compte source ou destination extérieur au registre : utiliser `encaisser`
  ou `decaisser` sur le seul compte suivi, selon le sens. Ne pas créer un compte
  fictif ni supprimer la protection contre les transferts entre entreprises.
- Frais effectivement débités : enregistrer un décaissement distinct du
  principal, avec sa propre clé d'idempotence et une référence reliant les deux
  écritures au justificatif externe. Ne pas appliquer 0,8 % par défaut.
- Frais confirmés nuls : ne pas créer de mouvement à zéro, refusé par les
  services. Conserver la preuve du tarif nul dans l'objet d'opération ou le
  justificatif du connecteur externe.
- Une anomalie tarifaire constatée doit rester visible dans les flux réels et
  être signalée par la couche de contrôle ; ne pas réécrire le relevé ou le
  montant historique pour le rendre artificiellement conforme.

Si le principal et les frais doivent être enregistrés ensemble, le projet hôte
peut envelopper les appels internes dans une transaction Django. Cette
transaction ne rend pas atomique un appel réseau chez un participant.

`source_system`, `source_type`, `source_id` / `external_source_id` et
`source_reference` relient les écritures à l'opération externe. Ils ne remplacent
pas les données structurées et preuves conservées par le connecteur. Un retry
doit réutiliser la même clé et le même payload, y compris les références.
Pour plusieurs mouvements d'une même opération, utiliser des clés distinctes
par compte et composante : les clés des mouvements sont uniques par entreprise.

### Séparer fournisseur commercial et rail

Orange Money, Moov Money, Wave ou une banque restent des `FinancialProvider`.
PI-SPI désigne le rail utilisé pour une opération. Il ne faut ni remplacer les
providers existants par `PI_SPI`, ni ajouter un faux provider représentant ce
rail. Le pays d'un provider et `selectable=True` ne certifient pas l'éligibilité
de l'opération ou l'adhésion d'un établissement à PI-SPI.

Lorsqu'un véritable connecteur sera demandé, son objet d'opération devra
conserver séparément fournisseur commercial, identité du participant, rail,
identités et pays des parties, nature de l'opération, instant d'exécution,
référence externe et détails du tarif appliqué. Ces informations ne sont pas
ajoutées au registre par anticipation.

Ne pas utiliser `transfert_effectue` comme une instruction d'envoyer de l'argent :
il est émis après le commit local. Une panne du handler ne retire pas les
écritures déjà enregistrées. Les signaux Django ne constituent pas une file
durable de paiement ni une preuve de règlement externe.

## Idempotence et rapprochement : garanties exactes

L'idempotence optionnelle est déjà isolée par entreprise et assortie d'un hash
du payload. Même clé et même payload retournent l'objet existant ; un payload
différent provoque `IdempotencyConflict`, traduit en HTTP 409 par l'API REST.
Sans clé, ou avec une nouvelle clé, le registre peut accepter une nouvelle
écriture pour une même référence externe : ces références ne sont pas des clés
d'unicité. Ce mécanisme ne garantit pas l'idempotence d'un transfert réseau.

Le rapprochement est disponible pour les comptes Mobile Money dans l'UI,
malgré le nom `RapprochementBancaire`. Il faut distinguer ses capacités actuelles :

- `initialiser` calcule la somme signée des mouvements validés ou rapprochés
  compris dans la période, puis `ecart = solde_comptable - solde_releve`. Ce calcul
  n'ajoute pas `solde_initial` : ne pas lui attribuer une garantie générale de
  rapprochement du solde de clôture d'un portefeuille.
- `ajouter_ligne_releve` et `pointer` sont des actions manuelles ; il n'existe
  aucun appariement automatique sur une référence de transaction PI-SPI.
- `valider` exige que les lignes comptables soient pointées, puis choisit le
  statut selon la présence de lignes `RELEVE`. Il n'exige pas explicitement
  `ecart == 0`. Le statut `EQUILIBRE` ne prouve donc ni l'absence d'écart de solde
  externe, ni le respect de la gratuité, ni l'exécution sur PI-SPI.

Ces limites préexistantes sont documentées ici ; elles ne sont pas transformées
en moteur de règlement ou corrigées indirectement par une règle tarifaire.

## Vérification et critères d'une future extension

Pour vérifier le registre existant, utiliser la suite du dépôt, en particulier :

- `tests/test_services.py::TransfertCompteServiceTest` : transfert, solde,
  même compte, protection inter-entreprises et retry idempotent.
- `tests/test_hardening.py::IntegrityHardeningTest` : conflit de payload,
  conservation des références et intégrité.
- `tests/test_services.py::RapprochementServiceTest` : somme signée des flux.
- `tests/test_api.py`, `tests/test_html_security.py` : API et accès HTML.
- `tests/test_concurrency.py::MovementConcurrencyTest` : retry concurrent
  d'un mouvement, uniquement sous PostgreSQL ; ce n'est pas un test de
  concurrence de transferts PI-SPI.

```bash
python -m django test tests --settings=tests.settings --verbosity 1
python -m django makemigrations --check --dry-run --settings=tests.settings
```

Aucun test de barème PI-SPI n'est ajouté à cette modification documentaire :
il n'existe aucun barème à tester. Aucune migration ou API n'est modifiée.

Vérification locale de cette modification : 92 tests découverts sur Python 3.12
et Django 5.2.17, 91 réussis et un test PostgreSQL ignoré sur SQLite ;
`makemigrations --check --dry-run` ne détecte aucun changement. Les garanties de
concurrence PostgreSQL n'ont pas été vérifiées par cette exécution locale.

Si une extension commence à router ou calculer des transferts, réouvrir cette
décision et couvrir au minimum les cas suivants dans cette couche :

| Domaine | Vérification attendue avant mise en service |
| --- | --- |
| Seuil | 7 999, 8 000 et 8 001 FCFA ; plusieurs opérations atteignant exactement le cumul quotidien puis le dépassant ; isolation par utilisateur et participant ; changement de journée et concurrence. |
| Tarification | Réception gratuite dans son périmètre ; taux d'émission configuré entre 0 et le plafond applicable, base hors taxes et arrondi documentés ; aucun frais obligatoire au plafond. |
| Dates | Avant, à et après le 2 novembre 2026 et le 1er juin 2027 ; instant réel de l'opération distinct de son import dans le registre ; national et intra-UEMOA distingués. |
| Routage | Rail PI-SPI distinct du provider ; classification explicite des parties et de l'opération ; absence de bascule silencieuse vers un rail non autorisé en cas de panne. |
| Idempotence | Retry réseau, confirmations dupliquées ou désordonnées, conflit de payload, panne entre confirmation externe et écriture locale ; un seul principal et un seul débit de frais. |
| Rapprochement | Référence et statut externes vérifiés, principal/frais/taxes rapprochés séparément, opérations échouées ou annulées et écarts visibles. |

Avant de coder le franchissement du seuil, l'application du cumul régional, les
taxes, les arrondis ou le traitement des opérations annulées, obtenir les règles
opérationnelles du participant. Le registre actuel ne fournit ni les identités
ni l'historique exhaustif nécessaires pour inventer ces choix.
