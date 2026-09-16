from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Partido, Pronostico

@receiver(post_save, sender=Partido)
def calcular_puntuacion_partido(sender, instance, **kwargs):
    # Verificamos si el partido cambió a estado 'FINALIZADO'
    if instance.estado == Partido.Estado.FINALIZADO and instance.goles_local is not None and instance.goles_visita is not None:
        pronosticos = Pronostico.objects.filter(partido=instance)
        
        pronosticos_actualizados = []
        for pronostico in pronosticos:
            puntos = 0
            
            goles_local = instance.goles_local
            goles_visita = instance.goles_visita
            pred_local = pronostico.goles_local_pred
            pred_visita = pronostico.goles_visita_pred
            
            diff_real = goles_local - goles_visita
            diff_pred = pred_local - pred_visita
            
            resultado_real_local_gana = diff_real > 0
            resultado_real_visita_gana = diff_real < 0
            resultado_real_empate = diff_real == 0
            
            resultado_pred_local_gana = diff_pred > 0
            resultado_pred_visita_gana = diff_pred < 0
            resultado_pred_empate = diff_pred == 0
            
            # 5 puntos: Marcador exacto
            if goles_local == pred_local and goles_visita == pred_visita:
                puntos = 5
            # Acertó el resultado
            elif (resultado_real_local_gana and resultado_pred_local_gana) or \
                 (resultado_real_visita_gana and resultado_pred_visita_gana) or \
                 (resultado_real_empate and resultado_pred_empate):
                
                # 4 puntos: Diferencia de goles correcta
                if diff_real == diff_pred:
                    puntos = 4
                # 3 puntos: Resultado correcto (ganador o empate) pero con marcador y diferencia distintos
                else:
                    puntos = 3
            else:
                # 0 puntos: Resultado incorrecto (fallo)
                puntos = 0
                
            pronostico.puntos_obtenidos = puntos
            pronosticos_actualizados.append(pronostico)
            
        if pronosticos_actualizados:
            Pronostico.objects.bulk_update(pronosticos_actualizados, ['puntos_obtenidos'])
