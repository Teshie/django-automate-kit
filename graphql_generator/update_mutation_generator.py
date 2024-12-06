import graphene

from .models import AutomateKitModel
from .mutation import MutationMixin
from .query_generator import QueryGenerator


class UpdateMutationGenerator(MutationMixin):
    @classmethod
    def generate_mutate_method_for_model(cls, model: AutomateKitModel):
        def _(root, info, *args, **kwargs):
            cls.check_permission(info.context.user, model)
            _input = kwargs.get("input")
            where = kwargs.get("where")
            _input = {x: _input[x] for x in _input if _input[x] is not None}

            if not where:
                raise Exception("you need to provide a where filter")

            built_query = QueryGenerator.query_set_builder(where)
            queryset = model.objects.filter(**built_query)

            updated_objects = []

            for obj in queryset:
                many_to_many_values = dict()
                for field_name, value in _input.items():
                    if field_name.endswith("_pk"):
                        field_name = field_name[:-3]
                        related_model = model._meta.get_field(field_name).related_model
                        try:
                            value = related_model.objects.get(pk=value)
                            setattr(obj, field_name, value)
                        except related_model.DoesNotExist:
                            raise Exception(
                                f"{related_model.__name__} with pk {value} does not exist."
                            )

                    elif field_name.endswith("_pks"):
                        field_name = field_name[:-4]
                        related_model = model._meta.get_field(field_name).related_model
                        related_objects = []
                        if not isinstance(value, list):
                            raise Exception(
                                f"{field_name}_pks must be list of related object"
                            )

                        for pk in value:
                            try:
                                related_objects.append(related_model.objects.get(pk=pk))
                            except related_model.DoesNotExist:
                                raise Exception(
                                    f"{related_model.__name__} with pk {value} does not exist."
                                )
                        many_to_many_values[field_name] = related_objects

                    else:
                        setattr(obj, field_name, value)
                obj.save()
                for mtm_key, mtm_value in many_to_many_values.items():
                    getattr(obj, mtm_key).set(mtm_value)
                updated_objects.append(obj)

            return {"data": updated_objects, "affected_rows": len(updated_objects)}

        return _

    @classmethod
    def generate_arguments_class_for_model(cls, model: AutomateKitModel, many=True):
        input_type = cls.generate_input_type(model, remove_required=True)
        where_clause = QueryGenerator.generate_where_clause_deep(model)(required=True)
        return type(
            "Arguments",
            (),
            {
                "inputs"
                if many
                else "input": graphene.List(input_type, required=True)
                if many
                else input_type(required=True),
                "where": where_clause,
            },
        )

    @classmethod
    def generate_query_for_model(cls, model: AutomateKitModel):
        argument_class = cls.generate_arguments_class_for_model(model, many=False)

        mutation_type = type(
            f"{cls.to_snake_case(model.__name__)}UpdateMutation",
            (graphene.Mutation,),
            {
                "Arguments": argument_class,
                "data": graphene.List(cls.get_or_generate_django_object_type(model)),
                "affected_rows": graphene.Int(),
                "mutate": cls.generate_mutate_method_for_model(model),
            },
        )

        setattr(
            cls, f"update_{cls.to_snake_case(model.__name__)}", mutation_type.Field()
        )
