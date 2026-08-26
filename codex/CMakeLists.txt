cmake_minimum_required(VERSION 3.28)
project(AletheiaCodex VERSION 1.0.0 LANGUAGES CXX C)

# Default to C++17 globally so dependencies like llama.cpp don't break with C++20 char8_t rules
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# ── llama.cpp backend selection ─────────────────────────────────────────────
# Default: link the PREBUILT llama.cpp b9102 release at Athenea\GGUF\llama.cpp
# (llama.dll + matching headers + MinGW import lib). No re-download, no llama.cpp
# source build; GPU offload via the shipped ggml-vulkan.dll backend.
option(CODEX_USE_PREBUILT_LLAMA
    "Link the prebuilt llama.cpp b9102 release instead of building from source" ON)

if (CODEX_USE_PREBUILT_LLAMA)
    set(CODEX_LLAMA_CPP_DIR "C:/McMaker Projects/Projects/Athenea/GGUF/llama.cpp" CACHE PATH
        "Prebuilt llama.cpp release directory (llama.dll, include/, lib/libllama.dll.a)")
    set(CODEX_LLAMA_IMPLIB "${CODEX_LLAMA_CPP_DIR}/lib/libllama.dll.a" CACHE FILEPATH
        "MinGW import library for the prebuilt llama.dll")

    if (NOT EXISTS "${CODEX_LLAMA_IMPLIB}")
        message(FATAL_ERROR
            "Prebuilt llama import library not found: ${CODEX_LLAMA_IMPLIB}\n"
            "Generate it from ${CODEX_LLAMA_CPP_DIR}/llama.dll with:\n"
            "  gendef llama.dll && dlltool -d llama.def -l libllama.dll.a --dllname llama.dll\n"
            "or configure with -DCODEX_USE_PREBUILT_LLAMA=OFF to build llama.cpp from source.")
    endif()

    add_library(llama SHARED IMPORTED)
    set_target_properties(llama PROPERTIES
        IMPORTED_LOCATION "${CODEX_LLAMA_CPP_DIR}/llama.dll"
        IMPORTED_IMPLIB "${CODEX_LLAMA_IMPLIB}"
        INTERFACE_INCLUDE_DIRECTORIES "${CODEX_LLAMA_CPP_DIR}/include"
        INTERFACE_SYSTEM_INCLUDE_DIRECTORIES "${CODEX_LLAMA_CPP_DIR}/include")
else()
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
endif()

# ── Application targets ─────────────────────────────────────────────────────
set(SOURCES
    src/main.cpp
    src/codex/latent_decipher.cpp
)

add_executable(aletheia_codex ${SOURCES})
add_executable(extraction_propup
    src/test_extraction_propup.cpp
    src/codex/extraction_module.cpp
)

# Task 4: sparse SAE projection propup — pure CPU, NO llama runtime.
add_executable(sae_propup
    src/test_sae_propup.cpp
    src/codex/sae_projection.cpp
)

# Apply C++23 standard ONLY to our code (dependencies stay at C++17)
set_target_properties(aletheia_codex PROPERTIES CXX_STANDARD 23)
set_target_properties(extraction_propup PROPERTIES CXX_STANDARD 23)
# Task 4 module is C++26 (GCC 16.1.0 accepts -std=c++26; CMake >= 3.30 supports it)
set_target_properties(sae_propup PROPERTIES CXX_STANDARD 26)

# sae_projection.cpp is compiled with the CPU SIMD ISA that this machine has:
# AVX2 + FMA + AVX-VNNI-INT8 (VPDPBSSD). Intel Ultra 9 275HX has NO AVX-512.
# -ffp-contract=off is MANDATORY for the no-noise guarantee: FMA contraction
# changes std::normal_distribution<float>'s internal rounding, flipping its
# reject/retry decisions and diverging the whole mt19937(42) weight stream away
# from the canonical kat_sae_scalar dictionary (byte-exact pinned by stage2
# anchor 1d7d32dc). The SIMD kernels use explicit _mm256_fmadd_ps intrinsics
# and are unaffected by the contraction setting.
set_source_files_properties(src/codex/sae_projection.cpp PROPERTIES
    COMPILE_OPTIONS "-mavx2;-mavxvnniint8;-mfma;-ffp-contract=off")

# Apply strict compilation flags only to our code
foreach (tgt aletheia_codex extraction_propup sae_propup)
    if (CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
        target_compile_options(${tgt} PRIVATE -Werror -Wpedantic -Wall -Wextra -fconcepts-diagnostics-depth=3 -fdiagnostics-show-template-tree -fdiagnostics-show-caret -fdiagnostics-color=always)
        # Statically link the MinGW runtime so a foreign libstdc++-6.dll on PATH
        # (e.g. Git's mingw64) can never be picked up at load time.
        target_link_options(${tgt} PRIVATE -static-libgcc -static-libstdc++ -static)
    elseif (MSVC)
        target_compile_options(${tgt} PRIVATE /WX /W4 /permissive- /diagnostics:caret /std:c++latest)
    endif()
endforeach()

# Link dependencies
target_link_libraries(aletheia_codex PRIVATE llama)
target_link_libraries(extraction_propup PRIVATE llama psapi)
target_include_directories(aletheia_codex PRIVATE src)
target_include_directories(extraction_propup PRIVATE src)
# sae_propup also includes TT_Tutor's verify headers (kat_anchors.hpp, #embed
# stage2 anchor) for the task4_kat pinned-anchor cross-check.
target_include_directories(sae_propup PRIVATE
    src
    "C:/McMaker Projects/Projects/Athenea/TT_Tutor/src")

# Ship the prebuilt llama runtime DLLs next to the propup binary
if (CODEX_USE_PREBUILT_LLAMA)
    file(GLOB CODEX_LLAMA_RUNTIME_DLLS "${CODEX_LLAMA_CPP_DIR}/*.dll")
    add_custom_command(TARGET extraction_propup POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${CODEX_LLAMA_RUNTIME_DLLS} $<TARGET_FILE_DIR:extraction_propup>)
endif()

# ── Propup + CTest registration (Task 3 QA gates) ───────────────────────────
include(CTest)
if (BUILD_TESTING)
    set(ATHENEA_GGUF_MODEL "C:/McMaker Projects/Projects/Athenea/GGUF/athenea-4b-coding-Q5_K_M.gguf" CACHE FILEPATH
        "Athenea GGUF model used by the extraction propup")
    set(ATHENEA_EVIDENCE_DIR "C:/McMaker Projects/Projects/Athenea/.omo/evidence" CACHE PATH
        "Directory where extraction propup evidence is written")

    add_test(NAME task3_extraction
        COMMAND extraction_propup extraction "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-3-extraction.txt")
    add_test(NAME task3_batch
        COMMAND extraction_propup batch "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-3-batch.txt")
    add_test(NAME task3_empty
        COMMAND extraction_propup empty "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-3-empty.txt")

    # Task 4: sparse SAE projection propup — pure CPU, no llama runtime.
    # The int8 dict file for the mmap/bench scenarios lives next to the build
    # binaries (a build artifact, not evidence).
    set(ATHENEA_SAE_DICT_FILE "${CMAKE_CURRENT_BINARY_DIR}/sae_dict_int8.bin" CACHE FILEPATH
        "Int8 SAE dictionary file used by the sae_propup mmap/bench scenarios")
    add_test(NAME task4_simd_match
        COMMAND sae_propup simd-match "${ATHENEA_EVIDENCE_DIR}/task-4-simd-match.txt" 131072)
    add_test(NAME task4_topk
        COMMAND sae_propup topk "${ATHENEA_EVIDENCE_DIR}/task-4-topk.txt" 16384)
    add_test(NAME task4_int8
        COMMAND sae_propup int8 "${ATHENEA_EVIDENCE_DIR}/task-4-int8.txt" 131072)
    add_test(NAME task4_mmap
        COMMAND sae_propup mmap "${ATHENEA_EVIDENCE_DIR}/task-4-mmap.txt" 131072 "${ATHENEA_SAE_DICT_FILE}")
    add_test(NAME task4_bench
        COMMAND sae_propup bench "${ATHENEA_EVIDENCE_DIR}/task-4-bench.txt" 131072 "${ATHENEA_SAE_DICT_FILE}")
    add_test(NAME task4_nodict
        COMMAND sae_propup nodict "${ATHENEA_EVIDENCE_DIR}/task-4-nodict.txt" 131072 "${ATHENEA_SAE_DICT_FILE}")
    add_test(NAME task4_kat
        COMMAND sae_propup kat "${ATHENEA_EVIDENCE_DIR}/task-4-kat.txt" 131072)

    # Task 12: extraction-stage contract gate. The blank/whitespace-prompt
    # scenario IS the contract check — extraction_module now rejects them with
    # std::invalid_argument (fail-closed pre-condition), and the module's
    # 2560D + finite-values post-checks run on every extract()/extract_batch().
    # Registered as its own gate so Task 12 verification is explicit.
    add_test(NAME task12_extraction_contracts
        COMMAND extraction_propup empty "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-12-extraction-contracts.txt")
endif()
