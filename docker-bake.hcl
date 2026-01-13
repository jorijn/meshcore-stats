variable "IMAGE_NAME" {
  default = "ghcr.io/jorijn/meshcore-stats"
}

variable "PLATFORMS" {
  default = "linux/amd64,linux/arm64"
}

variable "LOCAL_PLATFORM" {
  default = "linux/amd64"
}

variable "CACHE_FROM" {
  default = "type=local,src=.buildx-cache"
}

variable "CACHE_TO" {
  default = "type=local,dest=.buildx-cache,mode=max"
}

variable "VERSION" {
  default = "dev"
}

variable "VCS_REF" {
  default = "unknown"
}

variable "BUILD_DATE" {
  default = "1970-01-01T00:00:00Z"
}

variable "RELEASE_TAGS" {
  default = ""
}

target "base" {
  context = "."
  dockerfile = "Dockerfile"
  platforms = split(",", PLATFORMS)
  args = {
    VERSION = VERSION
    VCS_REF = VCS_REF
    BUILD_DATE = BUILD_DATE
  }
  cache-from = [CACHE_FROM]
  cache-to = [CACHE_TO]
}

target "pr-multiarch" {
  inherits = ["base"]
  output = ["type=cacheonly"]
}

target "pr-native" {
  inherits = ["base"]
  platforms = [LOCAL_PLATFORM]
  tags = ["meshcore-stats:pr"]
  output = ["type=docker"]
}

target "release" {
  inherits = ["base"]
  tags = RELEASE_TAGS != "" ? split(",", RELEASE_TAGS) : []
  push = true
}

target "nightly" {
  inherits = ["base"]
  tags = ["${IMAGE_NAME}:nightly"]
  push = true
}
