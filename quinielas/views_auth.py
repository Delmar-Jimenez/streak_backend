import string
import random
from rest_framework import status, views, generics
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from .serializers_auth import (
    RegisterSerializer, 
    RecuperarPasswordSerializer, 
    CambiarPasswordSerializer
)

Usuario = get_user_model()

def generate_random_password(length=10):
    """Genera una contraseña aleatoria de la longitud especificada."""
    chars = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(chars) for _ in range(length))

class RegisterView(generics.CreateAPIView):
    """
    Endpoint para registrar un nuevo usuario en la plataforma.
    """
    queryset = Usuario.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Endpoint de Login. Usa el comportamiento por defecto de SimpleJWT
    para generar y retornar los tokens access y refresh.
    """
    pass

class RecuperarPasswordView(views.APIView):
    """
    Endpoint para recuperar contraseña. Genera una temporal, actualiza el flag
    del usuario y simula el envío del correo electrónico.
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = RecuperarPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = Usuario.objects.get(email=email)
                
                # Generar contraseña temporal de 10 caracteres
                temp_password = generate_random_password(10)
                
                # Actualizar usuario
                user.set_password(temp_password)
                user.pass_temporal_flag = True
                user.save()
                
                # Simular envío por correo (En producción usar send_mail de django.core.mail)
                print(f"\n--- INICIO SIMULACIÓN DE CORREO ---")
                print(f"Para: {user.email}")
                print(f"Asunto: Recuperación de contraseña STREAK")
                print(f"Mensaje: Hola {user.username}, tu nueva contraseña temporal es: {temp_password}")
                print(f"Debes cambiarla la próxima vez que inicies sesión.")
                print(f"--- FIN SIMULACIÓN DE CORREO ---\n")
                
                return Response(
                    {"detail": "Se ha enviado una contraseña temporal a tu correo electrónico."},
                    status=status.HTTP_200_OK
                )
            except Usuario.DoesNotExist:
                # Buena práctica de seguridad: No revelar si el correo existe o no
                return Response(
                    {"detail": "Si el correo está registrado en nuestro sistema, se enviarán las instrucciones."},
                    status=status.HTTP_200_OK
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CambiarPasswordView(views.APIView):
    """
    Endpoint protegido para cambiar contraseña. Obligatorio si pass_temporal_flag = True.
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = CambiarPasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            old_password = serializer.validated_data['old_password']
            new_password = serializer.validated_data['new_password']
            
            # Verificar la contraseña actual (puede ser la temporal)
            if not user.check_password(old_password):
                return Response(
                    {"old_password": ["La contraseña actual no es correcta."]},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Establecer nueva contraseña
            user.set_password(new_password)
            user.pass_temporal_flag = False  # Resetear el flag ya que la ha cambiado
            user.save()
            
            return Response(
                {"detail": "Contraseña actualizada exitosamente. Ahora tienes acceso completo."},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
