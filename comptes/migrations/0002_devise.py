import csv
from pathlib import Path

import django.db.models.deletion
from django.db import migrations, models


def charger_devises_iso(apps, schema_editor):
    Devise = apps.get_model("comptes", "Devise")
    Compte = apps.get_model("comptes", "Compte")
    chemin = Path(__file__).resolve().parents[1] / "fixtures" / "iso4217.csv"
    symboles = {"XOF": "F CFA", "EUR": "€", "USD": "$", "GBP": "£"}

    with chemin.open(encoding="utf-8-sig", newline="") as fichier:
        lignes = csv.DictReader(fichier)
        for ligne in lignes:
            code = (ligne.get("AlphabeticCode") or "").strip()
            retrait = (ligne.get("WithdrawalDate") or "").strip()
            if not code or retrait:
                continue
            minor_unit = (ligne.get("MinorUnit") or "").strip()
            decimales = int(minor_unit) if minor_unit.isdigit() else 2
            Devise.objects.get_or_create(
                code=code,
                defaults={
                    "nom": (ligne.get("Currency") or code).strip(),
                    "code_numerique": (ligne.get("NumericCode") or "").strip(),
                    "decimales": decimales,
                    "symbole": symboles.get(code, ""),
                },
            )

    # Une ancienne base peut déjà contenir un code privé : on le conserve.
    for code in Compte.objects.exclude(devise="").values_list("devise", flat=True).distinct():
        Devise.objects.get_or_create(
            code=code,
            defaults={"nom": f"Devise personnalisée ({code})", "est_personnalisee": True},
        )


class Migration(migrations.Migration):
    dependencies = [("comptes", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Devise",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=10, unique=True, verbose_name="Code ISO")),
                ("nom", models.CharField(max_length=100, verbose_name="Nom")),
                ("code_numerique", models.CharField(blank=True, default="", max_length=3, verbose_name="Code numérique ISO")),
                ("decimales", models.PositiveSmallIntegerField(default=2, verbose_name="Décimales")),
                ("symbole", models.CharField(blank=True, default="", max_length=10, verbose_name="Symbole")),
                ("est_personnalisee", models.BooleanField(default=False, verbose_name="Devise personnalisée")),
                ("actif", models.BooleanField(default=True, verbose_name="Active")),
            ],
            options={"verbose_name": "Devise", "verbose_name_plural": "Devises", "ordering": ["code"]},
        ),
        migrations.RunPython(charger_devises_iso, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="compte",
            name="devise",
            field=models.ForeignKey(
                db_column="devise",
                default="XOF",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="comptes",
                to="comptes.devise",
                to_field="code",
                verbose_name="Devise",
            ),
        ),
    ]
