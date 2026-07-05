from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404

from ..models import Compte, JournalCompte
from ..services import JournalCompteService


@login_required
def journal_consulter(request, compte_id=None, date_journal=None):
    from datetime import date

    if date_journal is None:
        date_journal = date.today()

    if compte_id:
        compte = get_object_or_404(Compte, id=compte_id, actif=True)
        journal = JournalCompteService.obtenir_ou_creer(compte, date_journal)
        lignes = journal.lignes.all()
        JournalCompteService.alimenter_lignes(journal)
    else:
        journal = None
        lignes = []
        compte = None

    journaux_ouverts = JournalCompte.objects.filter(cloture=False).select_related("compte")

    context = {
        "journal": journal,
        "lignes": lignes,
        "compte": compte,
        "date_journal": date_journal,
        "journaux_ouverts": journaux_ouverts,
    }
    return render(request, "comptes/journal.html", context)
