from typing import Dict, List, Union
from rest_framework.response import Response
from rest_framework import views, status

def HTTP_200(data : Union[Dict, List[Dict]] ) -> Response:
    return Response({"data": data})

def HTTP_400(data : Union[Dict, List[Dict]] = None, message:dict = None) -> Response:

    return Response(
        message if message else {"data": data},
        status=status.HTTP_400_BAD_REQUEST
    )
