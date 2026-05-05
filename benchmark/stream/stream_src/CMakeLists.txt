cmake_minimum_required(VERSION 3.10)
project(stream C)

find_package(OpenMP REQUIRED)

add_executable(stream stream.c)

target_compile_options(stream PRIVATE
    -O3
    -DSTREAM_ARRAY_SIZE=20000000
    -DNTIMES=10
)

target_link_libraries(stream PRIVATE OpenMP::OpenMP_C)
