# test-openapi.ps1
param(
    [string]$Action = "validate",
    [string]$File = "openapi.yaml"
)

$CurrentDir = Get-Location

switch ($Action) {
    "validate" {
        Write-Host "🔍 Validating OpenAPI spec..." -ForegroundColor Yellow
        docker run --rm -v ${CurrentDir}:/app openapitools/openapi-generator-cli:latest validate -i /app/$File
    }
    "client-python" {
        Write-Host "🐍 Generating Python client..." -ForegroundColor Yellow
        docker run --rm -v ${CurrentDir}:/app openapitools/openapi-generator-cli:latest generate -i /app/$File -g python -o /app/client-python
    }
    "client-ts" {
        Write-Host "📘 Generating TypeScript client..." -ForegroundColor Yellow
        docker run --rm -v ${CurrentDir}:/app openapitools/openapi-generator-cli:latest generate -i /app/$File -g typescript-axios -o /app/client-ts
    }
    "docs" {
        Write-Host "📚 Generating HTML documentation..." -ForegroundColor Yellow
        docker run --rm -v ${CurrentDir}:/app openapitools/openapi-generator-cli:latest generate -i /app/$File -g html2 -o /app/docs
    }
    "server" {
        Write-Host "🚀 Generating Flask server stub..." -ForegroundColor Yellow
        docker run --rm -v ${CurrentDir}:/app openapitools/openapi-generator-cli:latest generate -i /app/$File -g python-flask -o /app/server
    }
    default {
        Write-Host "Unknown action: $Action" -ForegroundColor Red
        Write-Host "Available actions: validate, client-python, client-ts, docs, server" -ForegroundColor Yellow
    }
}