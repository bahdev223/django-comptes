from rest_framework import serializers

from ..models import (
    Compte, Devise, FinancialProvider, ModePaiement, MouvementCompte, TransfertCompte,
    JournalCompte, RapprochementBancaire, ClotureCompte,
)


class CompteSerializer(serializers.ModelSerializer):
    provider_code = serializers.CharField(source="provider.code", read_only=True)
    provider_name = serializers.CharField(source="provider.name", read_only=True)

    class Meta:
        model = Compte
        fields = [
            "id", "code", "nom", "provider", "provider_code", "provider_name",
            "identifiant", "type", "role",
            "devise", "taux_change", "devise_reference",
            "solde_initial", "solde_actuel", "solde_disponible",
            "accepte_ventes", "par_defaut",
            "actif", "autoriser_decouvert", "limite_decouvert",
            "date_ouverture", "date_fermeture",
            "compte_comptable_code", "entreprise_id",
        ]
        read_only_fields = ["solde_initial", "solde_actuel", "date_ouverture", "entreprise_id"]


class FinancialProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialProvider
        fields = [
            "id", "code", "name", "official_name", "kind", "country_code", "logo",
            "active", "selectable", "sort_order", "aliases", "metadata",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class DeviseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Devise
        fields = [
            "id", "code", "nom", "code_numerique", "decimales", "symbole",
            "est_personnalisee", "actif",
        ]


class ModePaiementSerializer(serializers.ModelSerializer):
    comptes = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Compte.objects.all(),
        required=False,
    )

    class Meta:
        model = ModePaiement
        fields = ["id", "entreprise_id", "code", "libelle", "actif", "comptes", "created_at", "updated_at"]
        read_only_fields = ["entreprise_id", "created_at", "updated_at"]


class MouvementInputSerializer(serializers.Serializer):
    compte_id = serializers.IntegerField()
    montant = serializers.DecimalField(max_digits=15, decimal_places=2)
    libelle = serializers.CharField(required=False, allow_blank=True, default="")
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    idempotency_key = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class AjustementInputSerializer(MouvementInputSerializer):
    sens = serializers.ChoiceField(choices=["ENTREE", "SORTIE"], required=False)


class TransfertInputSerializer(serializers.Serializer):
    source_id = serializers.IntegerField()
    destination_id = serializers.IntegerField()
    montant = serializers.DecimalField(max_digits=15, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    idempotency_key = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class MouvementCompteSerializer(serializers.ModelSerializer):
    compte_nom = serializers.CharField(source="compte.nom", read_only=True)
    compte_code = serializers.CharField(source="compte.code", read_only=True)

    class Meta:
        model = MouvementCompte
        fields = [
            "id", "compte", "compte_nom", "compte_code",
            "nature", "statut", "sens", "montant", "libelle",
            "reference", "idempotency_key", "date", "created_by",
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
