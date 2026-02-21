#!/bin/bash
# Chrome 실행에 필요한 라이브러리 설치 스크립트

echo "Chrome 의존성 패키지 설치 중..."
sudo apt-get update
sudo apt-get install -y \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2

echo "설치 완료!"
