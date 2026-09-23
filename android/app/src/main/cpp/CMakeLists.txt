cmake_minimum_required(VERSION 3.22.1)
project(hie_jni LANGUAGES CXX)

add_library(hie_jni SHARED hie_jni.cpp hie_pipeline.cpp)
target_compile_features(hie_jni PRIVATE cxx_std_17)
target_compile_options(hie_jni PRIVATE -O3 -ffast-math -fexceptions)
find_library(log-lib log)
target_link_libraries(hie_jni PRIVATE ${log-lib})
