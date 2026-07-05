import django.dispatch

mouvement_valide = django.dispatch.Signal()
mouvement_annule = django.dispatch.Signal()
transfert_effectue = django.dispatch.Signal()
compte_cloture = django.dispatch.Signal()
rapprochement_valide = django.dispatch.Signal()


def connecter_signaux():
    """
    Point d'entrée pour connecter les handlers par défaut.
    Les projets peuvent appeler cette fonction ou connecter
    leurs propres handlers via le mecanisme de Signal Django.
    """
    pass  # Les handlers métier sont définis dans handlers.py
