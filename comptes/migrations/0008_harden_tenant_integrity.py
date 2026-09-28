from django.db import migrations, models
from django.db.models import Q


LEGACY_M2M_TABLE = "comptes_modepaiement_comptes"


def _copy_legacy_payment_links(apps, schema_editor):
    tables = set(schema_editor.connection.introspection.table_names())
    if LEGACY_M2M_TABLE not in tables:
        return

    ModePaiementCompte = apps.get_model("comptes", "ModePaiementCompte")
    quote = schema_editor.connection.ops.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"SELECT modepaiement_id, compte_id FROM {quote(LEGACY_M2M_TABLE)}"
        )
        rows = cursor.fetchall()

    for mode_id, compte_id in rows:
        ModePaiementCompte.objects.get_or_create(
            mode_paiement_id=mode_id,
            compte_id=compte_id,
            defaults={"priorite": 0, "actif": True},
        )


def _backfill_tenants(apps, schema_editor):
    MouvementCompte = apps.get_model("comptes", "MouvementCompte")
    TransfertCompte = apps.get_model("comptes", "TransfertCompte")
    ModePaiement = apps.get_model("comptes", "ModePaiement")

    mouvements = []
    for obj in (
        MouvementCompte.objects.filter(entreprise_id="")
        .select_related("compte")
        .iterator(chunk_size=1000)
    ):
        if obj.compte.entreprise_id:
            obj.entreprise_id = obj.compte.entreprise_id
            mouvements.append(obj)
        if len(mouvements) >= 1000:
            MouvementCompte.objects.bulk_update(mouvements, ["entreprise_id"])
            mouvements = []
    if mouvements:
        MouvementCompte.objects.bulk_update(mouvements, ["entreprise_id"])

    transferts = []
    for obj in (
        TransfertCompte.objects.filter(entreprise_id="")
        .select_related("source")
        .iterator(chunk_size=1000)
    ):
        if obj.source.entreprise_id:
            obj.entreprise_id = obj.source.entreprise_id
            transferts.append(obj)
        if len(transferts) >= 1000:
            TransfertCompte.objects.bulk_update(transferts, ["entreprise_id"])
            transferts = []
    if transferts:
        TransfertCompte.objects.bulk_update(transferts, ["entreprise_id"])

    for mode in ModePaiement.objects.filter(entreprise_id="").iterator(chunk_size=500):
        tenant_ids = set(
            mode.comptes.exclude(entreprise_id="")
            .values_list("entreprise_id", flat=True)
            .distinct()
        )
        if len(tenant_ids) == 1:
            mode.entreprise_id = tenant_ids.pop()
            mode.save(update_fields=["entreprise_id"])


def _normalize_default_accounts(apps, schema_editor):
    Compte = apps.get_model("comptes", "Compte")
    tenant_ids = (
        Compte.objects.filter(par_defaut=True)
        .values_list("entreprise_id", flat=True)
        .distinct()
    )
    for tenant_id in tenant_ids:
        ids = list(
            Compte.objects.filter(
                entreprise_id=tenant_id,
                par_defaut=True,
            ).order_by("id").values_list("id", flat=True)
        )
        if len(ids) > 1:
            Compte.objects.filter(id__in=ids[1:]).update(par_defaut=False)


def forwards(apps, schema_editor):
    _copy_legacy_payment_links(apps, schema_editor)
    _backfill_tenants(apps, schema_editor)
    _normalize_default_accounts(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [
        ("comptes", "0007_modepaiementcompte_modepaiement_entreprise_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="transfertcompte",
            name="source_system",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="transfertcompte",
            name="source_type",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="transfertcompte",
            name="external_source_id",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="transfertcompte",
            name="source_reference",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="compte",
            constraint=models.UniqueConstraint(
                fields=("entreprise_id",),
                condition=Q(par_defaut=True),
                name="compte_defaut_unique_par_entreprise",
            ),
        ),
    ]
