#!/bin/bash
# Deploy rápido - Solo pull y restart

echo "🚀 Deploy Rápido - Solo código"
echo "================================"

cd /home/django/backend-accesories

echo "📥 Actualizando código..."
git pull

echo "🔄 Reiniciando aplicación..."
sudo supervisorctl restart backend_accesories

echo "✅ Deploy rápido completado!"
sudo supervisorctl status backend_accesories