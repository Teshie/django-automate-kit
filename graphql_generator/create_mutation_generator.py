from enum import Enum

import graphene

from .models import AutomateKitModel
from .mutation import MutationMixin


class CreateMutationGenerator(MutationMixin):
    @classmethod
    def resolve_related_object(
        cls, model: AutomateKitModel, field_name, value, info=None
    ):
        related_model = model._meta.get_field(field_name).related_model
        if related_model == cls.user_model() and value == "default_id":
            if info and info.context.user:
                value = info.context.user
            else:
                return None
                value = None

        try:
            return related_model.objects.get(pk=value)
        except related_model.DoesNotExist:
            raise Exception(f"{related_model.__name__} with pk {value} does not exist.")

    @classmethod
    def resolve_many_to_many_objects(
        cls, model: AutomateKitModel, field_name, value: list
    ):
        related_model = model._meta.get_field(field_name).related_model
        related_objects = []
        if not isinstance(value, list):
            raise Exception(f"{field_name}_pks must be list of related object")

        for pk in value:
            try:
                related_objects.append(related_model.objects.get(pk=pk))
            except related_model.DoesNotExist:
                raise Exception(
                    f"{related_model.__name__} with pk {value} does not exist."
                )

        return related_objects

    @classmethod
    def generate_mutate_method_for_model(cls, model: AutomateKitModel):
        def _(root, info, *args, **kwargs):
            cls.check_permission(info.context.user, model)
            inputs = kwargs.get("inputs")
            if isinstance(inputs, dict):
                inputs = [inputs]
            created_data = []
            for _input in inputs:
                model_instance = model()
                many_to_many_values = dict()
                for field_name, value in _input.items():
                    if isinstance(value, Enum):
                        value = value.value
                    if field_name.endswith("_pk"):
                        field_name = field_name[:-3]
                        related_object = cls.resolve_related_object(
                            model=model, field_name=field_name, value=value
                        )
                        if related_object:
                            setattr(model_instance, field_name, related_object)

                    elif field_name.endswith("_pks"):
                        field_name = field_name[:-4]
                        many_to_many_values[
                            field_name
                        ] = cls.resolve_many_to_many_objects(model, field_name, value)

                    else:
                        setattr(model_instance, field_name, value)
                model_instance.save()
                for mtm_key, mtm_value in many_to_many_values.items():
                    getattr(model_instance, mtm_key).set(mtm_value)
                created_data.append(model_instance)

            return {"data": created_data, "affected_rows": len(created_data)}

        return _

    @classmethod
    def generate_query_for_model(cls, model: AutomateKitModel):
        argument_class = cls.generate_arguments_class_for_model(model)

        mutation_type = type(
            f"{cls.to_snake_case(model.__name__)}CreateMutation",
            (graphene.Mutation,),
            {
                "Arguments": argument_class,
                "data": graphene.List(cls.get_or_generate_django_object_type(model)),
                "affected_rows": graphene.Int(),
                "mutate": cls.generate_mutate_method_for_model(model),
            },
        )

        setattr(
            cls, f"create_{cls.to_snake_case(model.__name__)}", mutation_type.Field()
        )
