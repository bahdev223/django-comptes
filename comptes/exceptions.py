class IdempotencyConflict(ValueError):
    """Une même clé d'idempotence a été réutilisée avec un payload différent."""

    pass
