cmake_minimum_required(VERSION 3.16)
project(edge_model_deploy VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

include_directories(include)

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

# 安装目标配置
install(TARGETS edge_model_deploy
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)
install(DIRECTORY include/ DESTINATION include)
