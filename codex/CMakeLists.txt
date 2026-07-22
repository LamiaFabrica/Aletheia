cmake_minimum_required(VERSION 3.28)
project(AletheiaCodex VERSION 1.0.0 LANGUAGES CXX C)

# Default to C++17 globally so dependencies like llama.cpp don't break with C++20 char8_t rules
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Strict flags are applied directly to the target below

# Fetch dependencies (llama.cpp)
include(FetchContent)
FetchContent_Declare(
    llama
    GIT_REPOSITORY https://github.com/ggerganov/llama.cpp.git
    GIT_TAG        master
)

# Avoid building llama.cpp examples/tests and explicitly disable its WERROR
set(LLAMA_BUILD_TESTS OFF CACHE BOOL "Disable llama.cpp tests" FORCE)
set(LLAMA_BUILD_EXAMPLES OFF CACHE BOOL "Disable llama.cpp examples" FORCE)
set(LLAMA_BUILD_SERVER OFF CACHE BOOL "Disable llama.cpp server" FORCE)
set(LLAMA_WERROR OFF CACHE BOOL "Disable llama.cpp WERROR" FORCE)
set(LLAMA_FATAL_WARNINGS OFF CACHE BOOL "Disable llama.cpp fatal warnings" FORCE)
set(GGML_WERROR OFF CACHE BOOL "Disable ggml WERROR" FORCE)
set(GGML_FATAL_WARNINGS OFF CACHE BOOL "Disable ggml fatal warnings" FORCE)

FetchContent_MakeAvailable(llama)

# Add our source files
set(SOURCES
    src/main.cpp
    src/codex/latent_decipher.cpp
)

add_executable(aletheia_codex ${SOURCES})

# Apply C++23/26 standard ONLY to our code
set_target_properties(aletheia_codex PROPERTIES CXX_STANDARD 23)

# Apply strict compilation flags only to our code
if (CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
    target_compile_options(aletheia_codex PRIVATE -Werror -Wpedantic -Wall -Wextra -fconcepts-diagnostics-depth=3 -fdiagnostics-show-template-tree -fdiagnostics-show-caret -fdiagnostics-color=always)
elseif (MSVC)
    target_compile_options(aletheia_codex PRIVATE /WX /W4 /permissive- /diagnostics:caret /std:c++latest)
endif()

# Link dependencies
target_link_libraries(aletheia_codex PRIVATE llama)
target_include_directories(aletheia_codex PRIVATE src)
