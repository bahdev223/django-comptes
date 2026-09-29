from datetime import date

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from ..models import JournalCompte
from ..services import JournalCompteService
from .security import get_scoped_compte_or_404, scoped_queryset


@login_required
@permission_required("comptes.view_journalcompte", raise_exception=True)
def journal_consulter(request, compte_id=None, date_journal=None):
    date_journal = date_journal or date.today()

    if compte_id:
        compte = get_scoped_compte_or_404(request, pk=compte_id, actif=True)
        journal = JournalCompteService.obtenir_ou_creer(compte, date_journal)
        JournalCompteService.alimenter_lignes(journal)
        lignes = journal.lignes.all()
    else:
        journal = None
        lignes = []
        compte = None

    journaux_ouverts = scoped_queryset(
        request,
        JournalCompte.objects.filter(cloture=False).select_related("compte"),
        field="compte__entreprise_id",
    )

    return render(
        request,
        "comptes/journal.html",
        {
            "journal": journal,
            "lignes": lignes,
            "compte": compte,
            "date_journal": date_journal,
            "journaux_ouverts": journaux_ouverts,
        },
    )
