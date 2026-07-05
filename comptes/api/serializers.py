from rest_framework import serializers

from ..models import (
    Compte, MouvementCompte, TransfertCompte,
    JournalCompte, RapprochementBancaire, ClotureCompte,
)


class CompteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Compte
        fields = [
            "id", "code", "nom", "type", "role",
            "devise", "taux_change", "devise_reference",
            "solde_actuel", "solde_disponible",
            "actif", "autoriser_decouvert", "limite_decouvert",
            "date_ouverture", "date_fermeture",
            "compte_comptable_code",
        ]
        read_only_fields = ["solde_actuel", "date_ouverture"]


class MouvementCompteSerializer(serializers.ModelSerializer):
    compte_nom = serializers.CharField(source="compte.nom", read_only=True)
    compte_code = serializers.CharField(source="compte.code", read_only=True)

    class Meta:
        model = MouvementCompte
        fields = [
            "id", "compte", "compte_nom", "compte_code",
            "nature", "statut", "montant", "libelle",
            "reference", "date", "created_by",
            "annule", "annule_le", "mouvement_parent",
        ]
        read_only_fields = ["date", "annule", "annule_le"]


class TransfertCompteSerializer(serializers.ModelSerializer):
    source_nom = serializers.CharField(source="source.nom", read_only=True)
    destination_nom = serializers.CharField(source="destination.nom", read_only=True)

    class Meta:
        model = TransfertCompte
        fields = "__all__"
        read_only_fields = ["date", "reference"]


class JournalCompteSerializer(serializers.ModelSerializer):
    compte_nom = serializers.CharField(source="compte.nom", read_only=True)

    class Meta:
        model = JournalCompte
        fields = "__all__"


class RapprochementBancaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = RapprochementBancaire
        fields = "__all__"


class ClotureCompteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClotureCompte
        fields = "__all__"
