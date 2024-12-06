import graphene
from django.db import models

from .models import AutomateKitModel
from .types import TypeGenerator


class MutationMixin(TypeGenerator, graphene.ObjectType):
    @classmethod
    def map_field_to_graphene_type(cls, field, required=False, default_value=None):
        type_mapping = {
            "CharField": graphene.String,
            "IntegerField": graphene.Int,
            "BooleanField": graphene.Boolean,
            "DateField": graphene.String,
            "DateTimeField": graphene.String,
            "DecimalField": graphene.Float,
            "EmailField": graphene.String,
            "FileField": graphene.String,
            "FloatField": graphene.Float,
            "ImageField": graphene.String,
            "PositiveIntegerField": graphene.Int,
            "PositiveSmallIntegerField": graphene.Int,
            "SlugField": graphene.String,
            "SmallIntegerField": graphene.Int,
            "TextField": graphene.String,
            "TimeField": graphene.String,
            "UUIDField": graphene.String,
            "BigIntegerField": graphene.Int,
            "BinaryField": graphene.String,
            "PositiveBigIntegerField": graphene.Int,
            "PositiveDecimalField": graphene.Float,
            "URLField": graphene.String,
            "AutoField": graphene.Int,
            "BigAutoField": graphene.Int,
            "ForeignKey": graphene.String,
        }
        internal_type = field.get_internal_type()

        if internal_type == "CharField" and field.choices is not None:
            query_name = f"{field.name}_enum"
            return type(
                query_name,
                (graphene.Enum,),
                {x[0]: x[0] for x in field.choices},
            )(required=required)

        if field.get_internal_type() in [
            "ForeignKey",
            "OneToOneField",
            "ManyToManyField",
        ]:
            related_model = field.related_model
            pk_field = related_model._meta.pk
            mapped_type = cls.map_field_to_graphene_type(
                pk_field, required=required, default_value=default_value
            )

            if field.get_internal_type() == "ManyToManyField":
                return graphene.List(
                    mapped_type.__class__,
                    required=required,
                    default_value=default_value,
                )

            return mapped_type

        if _mapped_type := type_mapping.get(field.get_internal_type()):
            return _mapped_type(required=required, default_value=default_value)

    @classmethod
    def generate_arguments_class_for_model(cls, model: AutomateKitModel, many=True):
        input_type = cls.generate_input_type(model)
        return type(
            "Arguments",
            (),
            {
                "inputs"
                if many
                else "input": graphene.List(input_type, required=True)
                if many
                else input_type(required=True),
            },
        )

    @classmethod
    def generate_input_type(cls, model: AutomateKitModel, remove_required=False):
        input_fields = dict()

        for field in model._meta.get_fields():
            if not isinstance(field, models.Field):
                continue

            if field.get_internal_type() == "ManyToManyField":
                input_fields[f"{field.name}_pks"] = cls.map_field_to_graphene_type(
                    field
                )

            elif field.get_internal_type() in ["ForeignKey", "OneToOneField"]:
                default_value = None
                if field.related_model == cls.user_model():
                    default_value = "default_id"
                if remove_required:
                    # _mapped_type(required=required, default_value=default_value)
                    # input_fields[f"{field.name}_pk"] = cls.map_field_to_graphene_type(
                    #     field, default_value=default_value
                    # )
                    input_fields[f"{field.name}_pk"] = graphene.ID(default_value=default_value)
                else:
                    input_fields[f"{field.name}_pk"] = graphene.ID(default_value=default_value, required=not field.null)
                    # input_fields[f"{field.name}_pk"] = cls.map_field_to_graphene_type(
                    #     field, required=not field.null, default_value=default_value
                    # )
            else:
                if remove_required:
                    input_fields[field.name] = cls.map_field_to_graphene_type(field)
                else:
                    input_fields[field.name] = cls.map_field_to_graphene_type(
                        field, required=not field.null
                    )
        return type(
            f"{cls.to_snake_case(model.__name__)}InputType",
            (graphene.InputObjectType,),
            input_fields,
            required=True,
        )
