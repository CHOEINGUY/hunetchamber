
aux_source_directory(. DIR_FONTS_SRCS)
add_library(Fonts ${DIR_FONTS_SRCS})


target_include_directories(Fonts PUBLIC
  ${CMAKE_CURRENT_LIST_DIR}
)


target_link_libraries(Fonts PUBLIC 
  pico_stdlib 
)
