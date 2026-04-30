

aux_source_directory(. DIR_GUI_SRCS)

add_library(GUI ${DIR_GUI_SRCS})

target_include_directories(GUI PUBLIC
  ${CMAKE_CURRENT_LIST_DIR}
)


target_link_libraries(GUI PUBLIC 
  pico_stdlib 
  Fonts
)
