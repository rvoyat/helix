{{/* Nome base del chart */}}
{{- define "helix.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Nome completo delle risorse */}}
{{- define "helix.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/* Label comuni */}}
{{- define "helix.labels" -}}
app.kubernetes.io/name: {{ include "helix.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{/* Selector labels per un componente (arg = nome componente) */}}
{{- define "helix.selectorLabels" -}}
app.kubernetes.io/name: {{ include "helix.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* Nomi derivati dei service (usati come DNS interno) */}}
{{- define "helix.backend.fullname" -}}{{ include "helix.fullname" . }}-backend{{- end -}}
{{- define "helix.frontend.fullname" -}}{{ include "helix.fullname" . }}-frontend{{- end -}}
{{- define "helix.chromadb.fullname" -}}{{ include "helix.fullname" . }}-chromadb{{- end -}}
