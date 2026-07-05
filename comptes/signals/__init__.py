"""
Signaux du module comptes.

Le module comptes émet des signaux pour notifier les autres modules
sans créer de dépendances directes. Les autres modules (comptabilité,
notifications, audit) peuvent écouter ces signaux sans que comptes
les connaisse.

Signaux émis:
    - mouvement_valide: un mouvement vient d'être créé
    - mouvement_annule: un mouvement vient d'être annulé
    - transfert_effectue: un transfert inter-comptes vient d'être réalisé
    - compte_cloture: un compte vient d'être clôturé
    - rapprochement_valide: un rapprochement vient d'être validé
"""

default_app_config = "comptes.apps.ComptesConfig"
