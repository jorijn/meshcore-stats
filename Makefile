SHELL := /bin/sh

IMAGE_NAME ?= ghcr.io/jorijn/meshcore-stats
PLATFORMS ?= linux/amd64,linux/arm64
LOCAL_PLATFORM ?= $(shell (docker info -f '{{.OSType}}/{{.Architecture}}' 2>/dev/null || echo linux/amd64) | tr -d '[:space:]')
BUILD_DATE ?= $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
VCS_REF ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
VERSION ?= dev
CACHE_FROM ?= type=local,src=.buildx-cache
CACHE_TO ?= type=local,dest=.buildx-cache,mode=max

.PHONY: docker-build docker-buildx-all

docker-build:
	LOCAL_PLATFORM=$(LOCAL_PLATFORM) docker buildx bake pr-native \
		--set *.args.BUILD_DATE=$(BUILD_DATE) \
		--set *.args.VCS_REF=$(VCS_REF) \
		--set *.args.VERSION=$(VERSION) \
		--set *.cache-from=$(CACHE_FROM) \
		--set *.cache-to=$(CACHE_TO)

docker-buildx-all:
	PLATFORMS=$(PLATFORMS) docker buildx bake pr-multiarch \
		--set *.args.BUILD_DATE=$(BUILD_DATE) \
		--set *.args.VCS_REF=$(VCS_REF) \
		--set *.args.VERSION=$(VERSION) \
		--set *.cache-from=$(CACHE_FROM) \
		--set *.cache-to=$(CACHE_TO)
