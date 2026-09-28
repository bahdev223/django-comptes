from django.db import models


class ImmutableFinancialQuerySet(models.QuerySet):
    """Bloque les mutations bulk qui contourneraient Model.save()."""

    def update(self, **kwargs):
        raise ValueError(
            "Les écritures financières ne peuvent pas être modifiées avec QuerySet.update()."
        )

    def delete(self):
        raise ValueError(
            "Les écritures financières ne peuvent pas être supprimées en masse."
        )

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValueError(
            "Les écritures financières ne peuvent pas être modifiées avec bulk_update()."
        )


class ImmutableFinancialManager(models.Manager.from_queryset(ImmutableFinancialQuerySet)):
    pass
