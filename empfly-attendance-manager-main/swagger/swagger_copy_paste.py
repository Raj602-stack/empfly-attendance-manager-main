# ! LIST

@swagger_auto_schema(
        tags=["Trips"],
        operation_id="List all trips",
        responses={
            200: serializer_class(many=True),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[
            SchemaParameters.get_page(),
            SchemaParameters.get_per_page(),
        ],
    )


# ! CREATE


@swagger_auto_schema(
        tags=["Objects"],
        operation_id="Create object",
        responses={
            201: serializer_class(),
            400: SchemaResponse.get_response(
                {"message": "Failed to create object"}, description="Failed"
            ),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        request_body=Schema(
            properties={
                "name": Schema(
                    description="Name of the object",
                    type=openapi.TYPE_STRING,
                ),
                "description": Schema(
                    description="Description of the object",
                    type=openapi.TYPE_STRING,
                ),
            },
            type=openapi.TYPE_OBJECT,
            required=["name"],
        )
    )




# ! READ

@swagger_auto_schema(
        tags=["Trips"],
        operation_id="Get a trip",
        responses={
            200: serializer_class(),
            404: SchemaResponse.get_404("trip"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[SchemaParameters.get_uuid("trip")],
    )


# ! UPDATE
@swagger_auto_schema(
        tags=["Objects"],
        operation_id="Update a object",
        responses={
            200: serializer_class(),
            404: SchemaResponse.get_404("object"),
            409: SchemaResponse.get_409("object", "name"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[
            SchemaParameters.get_uuid("group"),
        ],
        request_body=Schema(
            properties={
                "name": Schema(
                    description="Name of the group", type=openapi.TYPE_STRING
                ),
                "description": Schema(
                    description="Description of the group", type=openapi.TYPE_STRING
                ),
            },
            type=openapi.TYPE_OBJECT,
            required=[],
        ),
    )

# ! DELETE

@swagger_auto_schema(
        tags=["Members"],
        operation_id="Delete a member",
        responses={
            200: SchemaResponse.get_200_delete("member"),
            404: SchemaResponse.get_404("member"),
            429: SchemaResponse.get_429(),
            500: SchemaResponse.get_500(),
        },
        manual_parameters=[SchemaParameters.get_uuid("member")],
    )
