import graphene

from .models import AutomateKitModel
from .mutation import MutationMixin
from .query_generator import QueryGenerator


class DeleteMutationGenerator(MutationMixin):
    @classmethod
    def generate_mutate_method_for_model(cls, model: AutomateKitModel):
        def _(root, info, *args, **kwargs):
            cls.check_permission(info.context.user, model)
            where = kwargs.get("where")

            if not where:
                raise Exception("you need to provide a where filter")

            built_query = QueryGenerator.query_set_builder(where)
            queryset = model.objects.filter(**built_query)
            count = queryset.count()

            queryset.delete()

            return {"affected_rows": count}

        return _

    @classmethod
    def generate_arguments_class_for_model(cls, model: AutomateKitModel, many=True):
        where_clause = QueryGenerator.generate_where_clause_deep(model)(required=True)
        return type("Arguments", (), {"where": where_clause})

    @classmethod
    def generate_query_for_model(cls, model: AutomateKitModel):
        argument_class = cls.generate_arguments_class_for_model(model, many=False)

        mutation_type = type(
            f"{cls.to_snake_case(model.__name__)}DeleteMutation",
            (graphene.Mutation,),
            {
                "Arguments": argument_class,
                "affected_rows": graphene.Int(),
                "mutate": cls.generate_mutate_method_for_model(model),
            },
        )

        setattr(
            cls, f"delete_{cls.to_snake_case(model.__name__)}", mutation_type.Field()
        )
