add_library(lvgl_ui INTERFACE)

aux_source_directory(${CMAKE_CURRENT_LIST_DIR}  DIR_LVGL_UI_SRCS)
aux_source_directory(${CMAKE_CURRENT_LIST_DIR}/screen DIR_LVGL_UI_SRCS)
aux_source_directory(${CMAKE_CURRENT_LIST_DIR}/image DIR_LVGL_UI_SRCS)

target_include_directories(lvgl_ui INTERFACE
  ${CMAKE_CURRENT_LIST_DIR}
  ${CMAKE_CURRENT_LIST_DIR}/screen
)

target_sources(lvgl_ui INTERFACE
  ${DIR_LVGL_UI_SRCS}
)

target_link_libraries(lvgl_ui INTERFACE 
    bsp
    lvgl)
