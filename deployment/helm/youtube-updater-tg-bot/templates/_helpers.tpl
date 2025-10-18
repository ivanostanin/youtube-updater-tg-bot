{{/*
Expand the name of the chart.
*/}}
{{- define "youtube-updater-tg-bot.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "youtube-updater-tg-bot.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "youtube-updater-tg-bot.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "youtube-updater-tg-bot.labels" -}}
helm.sh/chart: {{ include "youtube-updater-tg-bot.chart" . }}
{{ include "youtube-updater-tg-bot.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "youtube-updater-tg-bot.selectorLabels" -}}
app.kubernetes.io/name: {{ include "youtube-updater-tg-bot.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "youtube-updater-tg-bot.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "youtube-updater-tg-bot.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the persistent volume claim to use
*/}}
{{- define "youtube-updater-tg-bot.pvcName" -}}
{{- if .Values.persistence.existingClaim }}
{{- .Values.persistence.existingClaim }}
{{- else }}
{{- include "youtube-updater-tg-bot.fullname" . }}-data
{{- end }}
{{- end }}

{{/*
Create secret name for bot credentials
*/}}
{{- define "youtube-updater-tg-bot.secretName" -}}
{{- if .Values.externalSecrets.enabled }}
{{- .Values.externalSecrets.target.name }}
{{- else }}
{{- include "youtube-updater-tg-bot.fullname" . }}-secrets
{{- end }}
{{- end }}

{{/*
Create configmap name
*/}}
{{- define "youtube-updater-tg-bot.configMapName" -}}
{{- include "youtube-updater-tg-bot.fullname" . }}-config
{{- end }}