from django import template
from django.template.defaultfilters import floatformat

register = template.Library()


@register.filter
def devise(montant, devise="XOF"):
    """Affiche un montant avec sa devise : '1 500 XOF'"""
    try:
        val = floatformat(montant, 0)
        return f"{val} {devise}"
    except (ValueError, TypeError):
        return montant


@register.filter
def sens_html(nature):
    """Retourne le sens (+/-) pour une nature de mouvement."""
    entrees = {"ENCAISSEMENT", "TRANSFERT", "AJUSTEMENT", "OUVERTURE"}
    if nature in entrees:
        return "+"
    return "−"


@register.filter
def classe_statut(statut):
    mapping = {
        "VALIDE": "text-green-600 bg-green-50",
        "ANNULE": "text-red-600 bg-red-50",
        "RAPPROCHE": "text-blue-600 bg-blue-50",
        "BROUILLON": "text-gray-600 bg-gray-50",
    }
    return mapping.get(statut, "text-gray-600 bg-gray-50")


@register.filter
def solde_class(solde):
    if solde > 0:
        return "text-green-600"
    if solde < 0:
        return "text-red-600"
    return "text-gray-600"
