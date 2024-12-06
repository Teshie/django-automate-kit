import graphene
from django.db import models

from .filters import AggregateType
from .models import AutomateKitModel
from .types import TypeGenerator


class QueryGenerator(graphene.ObjectType, TypeGenerator):
    @classmethod
    def include_apps(cls, apps: list):
        models = cls.find_all_models(_apps=apps)
        for model in models:
            cls.generate_query_for_model(model=model)

    @classmethod
    def include_models(cls, models: list):
        super().include_models(models=models)

    @classmethod
    def generate_resolve_method_for_model(
        cls, model: AutomateKitModel, is_aggregate=False
    ):
        def _(root, info, *args, **kwargs):
            cls.check_permission(info.context.user, model)
            where = kwargs.get("where")
            orderby = kwargs.get("orderby")
            offset = kwargs.get("offset")
            limit = kwargs.get("limit")

            queryset = model.objects.all()
            query = cls.query_set_builder(where)
            queryset = queryset.filter(**query)

            if offset:
                queryset = queryset[offset:]

            if limit:
                queryset = queryset[:limit]

            if orderby:
                queryset = queryset.order_by(orderby.value)

            if is_aggregate:
                return {"count": queryset.count()}

            return queryset

        return _

    @classmethod
    def generate_enum_query_for_model(cls, model: AutomateKitModel):
        for field in model._meta.get_fields():
            if not isinstance(field, models.Field):
                continue

            internal_type = field.get_internal_type()

            if internal_type == "CharField" and field.choices is not None:
                query_name = f"enums_{cls.to_snake_case(model.__name__)}_{field.name}"
                setattr(
                    cls,
                    query_name,
                    graphene.List(
                        graphene.String,
                        default_value=tuple([x[0] for x in field.choices]),
                    ),
                )

    @classmethod
    def generate_query_for_model(cls, model: AutomateKitModel):
        model_type = cls.get_or_generate_django_object_type(model=model)
        query_name = cls.to_snake_case(model.__name__)
        resolve_method = cls.generate_resolve_method_for_model(model=model)
        aggregate_resolve_method = cls.generate_resolve_method_for_model(
            model=model, is_aggregate=True
        )
        where_clause = cls.generate_where_clause_deep(model)()
        orderby_clause = cls.generate_orderby_clause(model)

        setattr(
            cls,
            query_name,
            graphene.List(
                model_type,
                where=where_clause,
                offset=graphene.Int(),
                limit=graphene.Int(),
                orderby=orderby_clause,
            ),
        )

        setattr(
            cls,
            f"{query_name}_aggregate",
            graphene.Field(AggregateType, where=where_clause),
        )

        setattr(cls, f"resolve_{query_name}", resolve_method)
        setattr(cls, f"resolve_{query_name}_aggregate", aggregate_resolve_method)
        cls.generate_enum_query_for_model(model)
