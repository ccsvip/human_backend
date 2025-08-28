from tortoise import fields, models


class WakeWord(models.Model):
    id = fields.IntField(pk=True)
    word = fields.CharField(max_length=255, unique=True)
    description = fields.CharField(max_length=255, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "wake_word"


