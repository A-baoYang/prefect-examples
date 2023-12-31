<template>
  <ListItem class="list-item-task-run" :icon="`pi-${stateType}`">
    <!-- For a later date... maybe -->
    <!-- :class="stateType + '-border'" -->

    <div class="list-item__title">
      <BreadCrumbs class="flex-grow-1" :crumbs="crumbs" tag="h2" />

      <div class="list-item-task-run__tag-container">
        <StateLabel :name="state.name" :type="state.type" class="mr-1" />
        <Tags :tags="tags" class="caption" />
      </div>
    </div>

    <div class="font--secondary list-item-task-run__duration">
      {{ duration }}
    </div>
  </ListItem>
</template>

<script lang="ts" setup>
import { computed } from 'vue'
import { Api, Query, Endpoints, TaskRunsFilter } from '@/plugins/api'
import { TaskRun } from '@/typings/objects'
import { secondsToApproximateString } from '@/util/util'
import StateLabel from '@/components/Global/StateLabel/StateLabel.vue'

const props = defineProps<{ item: TaskRun }>()

const taskRunFilterBody = computed<TaskRunsFilter>(() => {
  return {
    flow_runs: {
      id: {
        any_: [props.item.flow_run_id]
      }
    }
  }
})

const queries: { [key: string]: Query } = {
  flow_run: Api.query({
    endpoint: Endpoints.flow_runs,
    body: taskRunFilterBody.value
  }),
  flow: Api.query({
    endpoint: Endpoints.flows,
    body: taskRunFilterBody.value
  })
}

const state = computed(() => {
  return props.item.state
})

const stateType = computed(() => {
  return props.item.state.type.toLowerCase()
})

const tags = computed(() => {
  return props.item.tags
})

const flowRun = computed(() => {
  return queries.flow_run?.response?.value?.[0] || {}
})

const flow = computed(() => {
  return queries.flow?.response?.value?.[0] || {}
})

const duration = computed(() => {
  return stateType.value == 'pending' || stateType.value == 'scheduled'
    ? '--'
    : props.item.total_run_time
    ? secondsToApproximateString(props.item.total_run_time)
    : secondsToApproximateString(props.item.estimated_run_time)
})

const crumbs = computed(() => {
  return [
    { text: flow.value?.name },
    { text: flowRun.value?.name, to: `/flow-run/${flowRun.value?.id}` },
    { text: props.item.name }
  ]
})
</script>

<style lang="scss" scoped>
.list-item-task-run__duration {
  text-align: right;
  width: 75px;
  margin-left: auto;
}

.list-item-task-run__tag-container {
  margin-top: 2px;
  display: flex;
  white-space: nowrap;
}
</style>
