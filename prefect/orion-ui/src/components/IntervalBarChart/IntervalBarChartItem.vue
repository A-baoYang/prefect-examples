<template>
  <Popover
    class="interval-bar-chart-item"
    :placement="['bottom', 'top', 'leftTop', 'rightTop']"
  >
    <template v-slot:trigger="{ open, close }">
      <div
        class="interval-bar-chart-item__bucket"
        tabindex="0"
        @focusin="open"
        @focusout="close"
        @mouseenter="open"
        @mouseleave="close"
      />
    </template>
    <template v-slot:header>
      <div class="interval-bar-chart-item__popover-header">
        <slot name="popover-header" v-bind="item">
          <span>{{ title }}</span>
        </slot>
      </div>
    </template>
    <template v-slot:default>
      <div class="interval-bar-chart-item__popover-content">
        <slot name="popover-content" v-bind="item">
          <table class="table table--data">
            <tr>
              <td>Start Time:</td>
              <td>
                {{ formatDateTimeNumeric(item.interval_start) }}
              </td>
            </tr>
            <tr>
              <td>End Time:</td>
              <td>
                {{ formatDateTimeNumeric(item.interval_end) }}
              </td>
            </tr>
            <tr>
              <td>Value:</td>
              <td>{{ item.value }}</td>
            </tr>
          </table>
        </slot>
      </div>
    </template>
  </Popover>
</template>

<script lang="ts" setup>
import { IntervalBarChartItem } from './Types/IntervalBarChartItem'
import { formatDateTimeNumeric } from '@/utilities/dates'

const props = defineProps<{
  title: string
  item: IntervalBarChartItem
}>()
</script>

<style lang="scss">
@use '@/styles/abstracts/variables';

.interval-bar-chart-item {
  position: absolute;
  transform: translateX(50%);
}

.interval-bar-chart-item__bucket {
  background-color: $grey-40;
  border-radius: 999px;
  transition: all 150ms;
  transform-origin: bottom;
  z-index: 1;
  width: inherit;
  height: inherit;

  &:hover,
  &:focus {
    background-color: $primary;
  }
}

.interval-bar-chart-item__popover-header {
  font-size: 18px;
}

.interval-bar-chart-item__popover-content {
  font-size: 14px;
}
</style>
