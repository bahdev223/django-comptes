from django.db import models


class ComptesQuerySet(models.QuerySet):

    def actifs(self):
        return self.filter(actif=True)

    def par_type(self, type_compte):
        return self.filter(type=type_compte)

    def par_devise(self, code_devise):
        return self.filter(devise=code_devise)

    def avec_solde_positif(self):
        return self.filter(solde_actuel__gt=0)


class ComptesManager(models.Manager):

    def get_queryset(self):
        return ComptesQuerySet(self.model, using=self._db)

    def actifs(self):
        return self.get_queryset().actifs()

    def par_type(self, type_compte):
        return self.get_queryset().par_type(type_compte)

    def par_devise(self, code_devise):
        return self.get_queryset().par_devise(code_devise)

    def avec_solde_positif(self):
        return self.get_queryset().avec_solde_positif()
