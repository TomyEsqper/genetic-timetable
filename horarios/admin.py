# python
import logging
from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect

from .models import (
    ConfiguracionColegio, Profesor, DisponibilidadProfesor,
    Materia, MateriaProfesor, Grado, MateriaGrado,
    Curso, Aula, BloqueHorario, Horario
)

logger = logging.getLogger(__name__)

DIAS_SEMANA_CHOICES = [
    ('lunes', 'Lunes'),
    ('martes', 'Martes'),
    ('miércoles', 'Miércoles'),
    ('jueves', 'Jueves'),
    ('viernes', 'Viernes'),
]


class DisponibilidadProfesorAddForm(forms.ModelForm):
    dias_semana = forms.MultipleChoiceField(
        choices=DIAS_SEMANA_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Días de la semana',
        help_text='Marca los días que tendrán la misma disponibilidad',
    )

    class Meta:
        model = DisponibilidadProfesor
        fields = ['profesor', 'bloque_inicio', 'bloque_fin', 'dia']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['dia'].required = False
        self.fields['dia'].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        bi = cleaned.get('bloque_inicio')
        bf = cleaned.get('bloque_fin')
        if bi is None or bf is None:
            raise forms.ValidationError('Debes indicar bloque_inicio y bloque_fin.')
        if bi > bf:
            raise forms.ValidationError('El bloque de inicio no puede ser mayor que el bloque de fin.')
        dias = cleaned.get('dias_semana') or []
        if not dias:
            raise forms.ValidationError('Selecciona al menos un día.')
        return cleaned

    def save(self, commit=True):
        return super().save(commit=False)


class DisponibilidadProfesorAdmin(admin.ModelAdmin):
    list_display = ('profesor', 'dia', 'bloque_inicio', 'bloque_fin')

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = DisponibilidadProfesorAddForm
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        if obj is None:
            return ['profesor', 'dias_semana', 'bloque_inicio', 'bloque_fin', 'dia']
        return ['profesor', 'dia', 'bloque_inicio', 'bloque_fin']

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)
            return

        profesor = form.cleaned_data.get('profesor')
        dias = form.cleaned_data.get('dias_semana') or []
        bi = form.cleaned_data.get('bloque_inicio')
        bf = form.cleaned_data.get('bloque_fin')

        existentes_qs = DisponibilidadProfesor.objects.filter(
            profesor=profesor,
            dia__in=dias,
            bloque_inicio=bi,
            bloque_fin=bf,
        ).values_list('dia', flat=True)
        dias_existentes = set(existentes_qs)

        to_create = []
        for d in dias:
            if d not in dias_existentes:
                to_create.append(
                    DisponibilidadProfesor(
                        profesor=profesor,
                        dia=d,
                        bloque_inicio=bi,
                        bloque_fin=bf,
                    )
                )

        created = 0
        if to_create:
            DisponibilidadProfesor.objects.bulk_create(to_create)
            created = len(to_create)

        omitidas = len(dias) - created

        self.message_user(
            request,
            f"Se crearon {created} disponibilidades ({omitidas} omitidas por duplicado).",
            level=messages.SUCCESS
        )
        if omitidas:
            self.message_user(
                request,
                f"Omitidas por duplicado: {omitidas}.",
                level=messages.WARNING
            )

        logger.info(
            "Disponibilidades creadas: %s, omitidas: %s | Profesor: %s | Días: %s | Bloques: %s-%s",
            created, omitidas, profesor, dias, bi, bf
        )

    def response_add(self, request, obj, post_url_continue=None):
        return HttpResponseRedirect(self.get_changelist_url())

    def get_changelist_url(self):
        from django.urls import reverse
        opts = self.model._meta
        return reverse(f'admin:{opts.app_label}_{opts.model_name}_changelist')


# ====== NUEVO: Alta masiva de MateriaGrado con checkboxes de Materias ======

class MateriaGradoAddForm(forms.ModelForm):
    materias = forms.ModelMultipleChoiceField(
        queryset=Materia.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Materias',
        help_text='Marca todas las materias que quieres asignar a este grado',
    )

    class Meta:
        model = MateriaGrado
        fields = ['grado', 'materia']  # mantenemos el campo original para edición

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # En creación ocultaremos 'materia' individual (lo controla el admin en get_form/get_fields)
        self.fields['materia'].required = False
        self.fields['materia'].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        materias = list(cleaned.get('materias') or [])
        if not cleaned.get('grado'):
            raise forms.ValidationError('Debes seleccionar un grado.')
        if not materias:
            raise forms.ValidationError('Selecciona al menos una materia.')

        # IMPORTANTE: asignar una materia “placeholder” para que la instancia temporal
        # que usa el admin no rompa al evaluar __str__ antes de guardar.
        cleaned['materia'] = materias[0]
        return cleaned

    def save(self, commit=True):
        return super().save(commit=False)


class MateriaGradoAdmin(admin.ModelAdmin):
    list_display = ('grado', 'materia')

    def get_form(self, request, obj=None, **kwargs):
        # Usamos el formulario con checkboxes solo en "add"
        if obj is None:
            kwargs['form'] = MateriaGradoAddForm
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        if obj is None:
            # En alta: grado + checkboxes de materias (oculto el campo materia base)
            return ['grado', 'materias', 'materia']
        # En edición normal: grado + materia única
        return ['grado', 'materia']

    def save_model(self, request, obj, form, change):
        if change:
            # Edición de una fila existente
            super().save_model(request, obj, form, change)
            return

        grado = form.cleaned_data.get('grado')
        materias = list(form.cleaned_data.get('materias') or [])

        # Detectar existentes (para evitar duplicados exactos)
        existentes_ids = set(
            MateriaGrado.objects.filter(
                grado=grado, materia__in=materias
            ).values_list('materia_id', flat=True)
        )

        to_create = [
            MateriaGrado(grado=grado, materia=m)
            for m in materias
            if m.id not in existentes_ids
        ]

        created = 0
        if to_create:
            MateriaGrado.objects.bulk_create(to_create)
            created = len(to_create)

        omitidas = len(materias) - created

        self.message_user(
            request,
            f"Se crearon {created} relaciones Materia–Grado ({omitidas} omitidas por duplicado).",
            level=messages.SUCCESS
        )
        if omitidas:
            self.message_user(
                request,
                f"Omitidas por duplicado: {omitidas}.",
                level=messages.WARNING
            )

        logger.info(
            "MateriaGrado creadas: %s, omitidas: %s | Grado: %s | Materias: %s",
            created, omitidas, grado, [m.id for m in materias]
        )

    def response_add(self, request, obj, post_url_continue=None):
        return HttpResponseRedirect(self.get_changelist_url())

    def get_changelist_url(self):
        from django.urls import reverse
        opts = self.model._meta
        return reverse(f'admin:{opts.app_label}_{opts.model_name}_changelist')


admin.site.register(ConfiguracionColegio)
admin.site.register(Profesor)
admin.site.register(DisponibilidadProfesor, DisponibilidadProfesorAdmin)
admin.site.register(Materia)
admin.site.register(MateriaProfesor)
admin.site.register(Grado)
admin.site.register(MateriaGrado, MateriaGradoAdmin)
admin.site.register(Curso)
admin.site.register(Aula)
admin.site.register(BloqueHorario)
admin.site.register(Horario)
