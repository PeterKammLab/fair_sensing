## Install and load the required packages
install.packages("ggplot2")
install.packages("dplyr")
install.packages("ggsci")
install.packages("rio")
install.packages("tidyverse")
install.packages("ggrepel")  # for smart label placement

install.packages("svglite")


# Load the required library
library(rio)
library(ggplot2)
library(tidyverse)
library(dplyr)
library(ggsci)
library(ggrepel)  # for smart label placement

#setwd("C:\Users\pkoljensic\OneDrive - Delft University of Technology\Desktop\PYTHON\projects\sensing\Fair_Sensing_Repo\data\temp
#")
setwd(dirname(rstudioapi::getActiveDocumentContext()$path))

#df <- import("intransit_titus_data25.csv")c:\Users\pkoljensic\OneDrive - Delft University of Technology\Desktop\FAIR EXPORTS\Tables Data\intransit_summary_19052025_7days_W.csv
#df <- import("intransit_petar_data.csv")
#df <- import("intransit_summary_21052025_1day_W.csv")
df <- import("intransit_summary_21052025_3days_W.csv")


##Spatial
p <- ggplot(df, aes(x = avg_point_spatial, y = unique_spatial,  size = Sample, color = Eucl_spatial,)) +
  geom_point(alpha = 0.8) +
  geom_line(aes(group = factor(Sample)), size = 1) +
  geom_text(aes(label = as.numeric(Sample)), vjust = -1, size = 3) +
  scale_color_gradient(
  low = "#85b66f",
  high = "#ffa3c4",
  trans = "log10",
  name = "Fairness") +
  scale_x_continuous(limits = c(0, 400)) +
  scale_y_continuous(limits = c(0, 3000)) +
  labs(x = "Frequency", y = "Spatial Count", color = "Fairness", size = "#Vehicles") +
  theme_minimal()

ggsave("intransit_spatial_new4.png", plot = p, width = 8, height = 6, dpi = 300, bg = "white")

##Spatial with all vehicles 
p <- ggplot(df, aes(x = avg_point_spatial, y = unique_spatial,  size = Sample, color = Eucl_spatial,)) +
  geom_point(alpha = 0.8) +
  geom_line(aes(group = factor(Sample)), size = 1) +
  geom_text(aes(label = as.numeric(Sample)), vjust = -1, size = 3) +
  scale_color_gradient(
  low = "#85b66f",
  high = "#ffa3c4",
  trans = "log10",
  name = "Fairness") +
  scale_x_continuous(limits = c(0, 750)) +
  scale_y_continuous(limits = c(2000, 3000)) +
  labs(x = "Frequency", y = "Spatial Count", color = "Fairness", size = "#Vehicles") +
  theme_minimal()

ggsave("intransit_spatial_new4.png", plot = p, width = 8, height = 6, dpi = 300, bg = "white")


##Temporal
b <- ggplot(df, aes(x = avg_point_temp, y = unique_temp, size = Sample, color = Eucl_temp, )) +
  geom_point(alpha = 0.8) +
  geom_line(aes(group = factor(Sample)), size = 1) +
  geom_text(aes(label = as.numeric(Sample)), vjust = -1, size = 3) +  # Adding labels directly
  scale_color_gradient(
  low = "#85b66f",
  high = "#ffa3c4",
  trans = "log10",
  name = "Fairness")  +
  scale_x_continuous(limits = c(0, 1500)) +
  scale_y_continuous(limits = c(0, 3000)) +
  labs(x = "Frequency", y = "Spatial Count", color = "Fairness", size = "#Vehicles") +
  theme_minimal()

ggsave("intransit_temporal4.png", plot = b, width = 8, height = 6, dpi = 300, bg = "white")


##Fairness
d <- ggplot(df, aes(x = avg_point_fair, y = unique_fair, size = Sample,  color = Eucl_fair, )) +
  geom_point(alpha = 0.8) +
  geom_line(aes(group = factor(Sample)), size = 1) +
  geom_text(aes(label = as.numeric(Sample)), vjust = -1, size = 3) +  # Adding labels directly
  scale_color_gradient(
  low = "#85b66f",
  high = "#ffa3c4",
  trans = "log10",
  name = "Fairness")  +
  scale_x_continuous(limits = c(0, 1000)) +
  scale_y_continuous(limits = c(0, 3000)) +
  labs(x = "Frequency", y = "Spatial Count", color = "Fairness", size = "#Vehicles") +
  theme_minimal()


ggsave("intransit_fair4.png", plot = d, width = 8, height = 6, dpi = 300, bg = "white")



## Prepare data in long format, with corresponding Eucl values
df_long <- df %>%
  mutate(Sample = as.numeric(Sample)) %>%
  select(Sample,
         avg_point_spatial, unique_spatial, Eucl_spatial,
         avg_point_temp, unique_temp, Eucl_temp,
         avg_point_fair, unique_fair, Eucl_fair) %>%
  tidyr::pivot_longer(
    cols = -Sample,
    names_to = c(".value", "type"),
    names_pattern = "(avg_point|unique|Eucl)_(spatial|temp|fair)"
  )

## Plot all in one 

ggplot(df_long, aes(x = avg_point, y = unique, color = Eucl, shape = type, size = Sample)) +
  geom_point(alpha = 0.8) +
  geom_text_repel(
    aes(label = Sample),
    max.overlaps = Inf,
    box.padding = 0.5,
    point.padding = 0.2,
    segment.color = NA,  # disables lines
    nudge_y = 55,        # always above the point
    #color = "black",     # black N if needed
    size = 3
  ) +
  scale_color_gradient(
    low = "#85b66f",
    high = "#ffa3c4",
    trans = "log10",
    name = "Fairness [Euclidean distance]"
  ) +
  scale_x_continuous(limits = c(0, 850)) +
  scale_y_continuous(limits = c(0, 3100)) +
  labs(
    x = "Frequency [avg. measurements per unique cell]",
    y = "Spatial coverage [unique cells]",
    shape = "Optimization",
    size = "#Vehicles"
  ) +
  theme_minimal() + 
  guides(
  shape = guide_legend(override.aes = list(size = 4))
  )
  

ggsave("intransit_allinone_3days.png", width = 8, height = 6, dpi = 300, bg = "white")
#ggsave("intransit_allinone_new6.svg", width = 8, height = 6, bg = "white")



