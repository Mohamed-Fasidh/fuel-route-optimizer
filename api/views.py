from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import RoutePlanRequestSerializer
from .services import RoutePlanningError, plan_route


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok"})


class RoutePlanView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = RoutePlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = plan_route(**serializer.validated_data)
            return Response(result, status=status.HTTP_200_OK)
        except RoutePlanningError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except Exception:
            return Response(
                {"error": "Unexpected route planning error."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
