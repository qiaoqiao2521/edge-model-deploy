cmake_minimum_required(VERSION 3.16)
project(edge_model_deploy VERSION 0.2.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/third_party/whisper.cpp/include/whisper.h")
    message(FATAL_ERROR "Missing whisper.cpp submodule. Run: git submodule update --init --recursive")
endif()

# The application library remains shared; upstream dependencies are static.
set(BUILD_SHARED_LIBS OFF CACHE BOOL "Build upstream dependencies statically" FORCE)
set(WHISPER_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_SERVER OFF CACHE BOOL "" FORCE)
set(WHISPER_CURL OFF CACHE BOOL "" FORCE)
set(WHISPER_COREML OFF CACHE BOOL "" FORCE)
set(WHISPER_OPENVINO OFF CACHE BOOL "" FORCE)
foreach(backend CUDA MUSA HIP VULKAN WEBGPU METAL RPC SYCL OPENCL ZDNN)
    set(GGML_${backend} OFF CACHE BOOL "CPU-only baseline" FORCE)
endforeach()
set(GGML_BACKEND_DL OFF CACHE BOOL "" FORCE)
set(GGML_CPU ON CACHE BOOL "" FORCE)
add_subdirectory(third_party/whisper.cpp EXCLUDE_FROM_ALL)

# 动态库与核心模块
add_library(edge_model_deploy SHARED
    src/hardware_detector.cpp
    src/whisper_engine.cpp
    src/dynamic_delivery.cpp
)

target_include_directories(edge_model_deploy PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_link_libraries(edge_model_deploy PRIVATE whisper)

add_executable(edge-transcribe tools/edge_transcribe.cpp)
target_link_libraries(edge-transcribe PRIVATE edge_model_deploy)
if(APPLE)
    set_target_properties(edge-transcribe PROPERTIES INSTALL_RPATH "@loader_path/../lib")
elseif(UNIX)
    set_target_properties(edge-transcribe PROPERTIES INSTALL_RPATH "$ORIGIN/../lib")
endif()

include(CTest)
if(BUILD_TESTING)
    add_executable(native-engine-tests tests/native_engine_test.cpp)
    target_link_libraries(native-engine-tests PRIVATE edge_model_deploy)
    add_test(NAME native-engine-boundaries COMMAND native-engine-tests)
    set(EDGE_TEST_MODEL "" CACHE FILEPATH "Optional verified model for native validation tests")
    if(EDGE_TEST_MODEL)
        add_test(NAME native-model-boundaries COMMAND native-engine-tests "${EDGE_TEST_MODEL}")
    endif()
endif()

# 安装目标配置
install(TARGETS edge_model_deploy edge-transcribe
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)
install(DIRECTORY include/ DESTINATION include)
