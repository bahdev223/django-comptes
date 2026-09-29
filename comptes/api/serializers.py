from rest_framework import serializers

from ..models import (
    ClotureCompte,
    Compte,
    Devise,
    FinancialProvider,
    JournalCompte,
    ModePaiement,
    MouvementCompte,
    RapprochementBancaire,
    TransfertCompte,
)
from ..scoping import resolve_entreprise_id, scoping_enabled
from ..services import CompteService


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

    def validate(self, attrs):
        instance = self.instance
        provider = attrs.get("provider", getattr(instance, "provider", None))
        type_compte = attrs.get("type", getattr(instance, "type", None))
        if provider is not None:
            from ..models import ProviderKind, TypeCompte
            expected = {
                ProviderKind.CASH: TypeCompte.ESPECES,
                ProviderKind.BANK: TypeCompte.BANQUE,
                ProviderKind.MOBILE_MONEY: TypeCompte.MOBILE_MONEY,
                ProviderKind.PAYMENT_INSTITUTION: TypeCompte.AUTRE,
            }.get(provider.kind)
            if expected and type_compte != expected:
                raise serializers.ValidationError({
                    "type": "Le type du compte est incompatible avec le fournisseur financier."
                })
        return attrs

    def update(self, instance, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return CompteService.modifier(
            instance,
            user=user,
            commentaire="Modification via API",
            **validated_data,
        )


class FinancialProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialProvider
        fields = [
            "id", "code", "name", "official_name", "kind", "country_code", "logo",
            "active", "selectable", "sort_order", "aliases", "metadata",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


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
        queryset=Compte.objects.none(),
        required=False,
    )

    class Meta:
        model = ModePaiement
        fields = [
            "id", "entreprise_id", "code", "libelle", "actif",
            "comptes", "created_at", "updated_at",
        ]
        read_only_fields = ["entreprise_id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Compte.objects.all()
        request = self.context.get("request")
        if scoping_enabled() and request is not None:
            qs = qs.filter(entreprise_id=resolve_entreprise_id(request))
        self.fields["comptes"].queryset = qs

    def validate_comptes(self, comptes):
        request = self.context.get("request")
        if not scoping_enabled() or request is None:
            return comptes
        entreprise_id = resolve_entreprise_id(request)
        invalides = [c.pk for c in comptes if c.entreprise_id != entreprise_id]
        if invalides:
            raise serializers.ValidationError(
                "Un mode de paiement ne peut être lié qu'aux comptes de l'entreprise active."
            )
        return comptes


class TraceInputSerializer(serializers.Serializer):
    source_system = serializers.CharField(required=False, allow_blank=True, default="")
    source_type = serializers.CharField(required=False, allow_blank=True, default="")
    source_id = serializers.CharField(required=False, allow_blank=True, default="")
    source_reference = serializers.CharField(required=False, allow_blank=True, default="")


class MouvementInputSerializer(TraceInputSerializer):
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
    source_system = serializers.CharField(required=False, allow_blank=True, default="")
    source_type = serializers.CharField(required=False, allow_blank=True, default="")
    external_source_id = serializers.CharField(required=False, allow_blank=True, default="")
    source_reference = serializers.CharField(required=False, allow_blank=True, default="")


class MouvementCompteSerializer(serializers.ModelSerializer):
    compte_nom = serializers.CharField(source="compte.nom", read_only=True)
    compte_code = serializers.CharField(source="compte.code", read_only=True)

    class Meta:
        model = MouvementCompte
        fields = [
            "id", "compte", "compte_nom", "compte_code",
            "nature", "statut", "sens", "montant", "libelle",
            "reference", "idempotency_key", "payload_hash", "date", "created_by",
            "annule", "annule_le", "mouvement_parent",
            "source_system", "source_type", "source_id", "source_reference",
        ]
        read_only_fields = fields


class TransfertCompteSerializer(serializers.ModelSerializer):
    source_nom = serializers.CharField(source="source.nom", read_only=True)
    destination_nom = serializers.CharField(source="destination.nom", read_only=True)

    class Meta:
        model = TransfertCompte
        fields = "__all__"
        read_only_fields = [field.name for field in TransfertCompte._meta.fields]


class JournalCompteSerializer(serializers.ModelSerializer):
    compte_nom = serializers.CharField(source="compte.nom", read_only=True)

    class Meta:
        model = JournalCompte
        fields = "__all__"
        read_only_fields = [field.name for field in JournalCompte._meta.fields]


class RapprochementBancaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = RapprochementBancaire
        fields = "__all__"
        read_only_fields = [field.name for field in RapprochementBancaire._meta.fields]


class RapprochementInitialiserSerializer(serializers.Serializer):
    compte_id = serializers.IntegerField()
    date_debut = serializers.DateField()
    date_fin = serializers.DateField()
    date_releve = serializers.DateField(required=False)
    solde_releve = serializers.DecimalField(max_digits=15, decimal_places=2)


class RapprochementLigneSerializer(serializers.Serializer):
    ligne_id = serializers.IntegerField()


class LigneReleveInputSerializer(serializers.Serializer):
    montant = serializers.DecimalField(max_digits=15, decimal_places=2)
    date_operation = serializers.DateField()
    libelle = serializers.CharField()
    commentaire = serializers.CharField(required=False, allow_blank=True, default="")


class ClotureCompteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClotureCompte
        fields = "__all__"
        read_only_fields = [field.name for field in ClotureCompte._meta.fields]


class ClotureInputSerializer(serializers.Serializer):
    compte_id = serializers.IntegerField()
    solde_reel = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, allow_null=True
    )
    commentaire = serializers.CharField(required=False, allow_blank=True, default="")
    date_cloture = serializers.DateField(required=False)
