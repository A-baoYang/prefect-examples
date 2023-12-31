<template>
  <Card class="menu font--primary" tabindex="0">
    <template v-if="!media.md" v-slot:header>
      <div class="pa-2 d-flex justify-center align-center">
        <h3 class="d-flex align-center font--secondary ml-auto">
          <i class="pi pi-search-line mr-1" />
          Search
        </h3>

        <IconButton
          icon="pi-close-line"
          height="34px"
          width="34px"
          flat
          class="ml-auto"
          style="border-radius: 50%"
          @click="close"
        />
      </div>
    </template>

    <div class="menu-content">
      <transition name="fade" mode="out-in">
        <div
          v-if="loading.value && !searches.length"
          class="
            my-6
            d-flex
            flex-column
            align-center
            justify-center
            font--secondary
          "
        >
          <Loader :loading="loading" />
        </div>
        <div
          v-else-if="error"
          class="
            my-6
            d-flex
            flex-column
            align-center
            justify-center
            font--secondary
          "
        >
          <i class="pi pi-error-warning-line pi-3x" />
          <h2>Couldn't fetch saved searches</h2>
        </div>
        <div v-else class="justify-self-start">
          <transition-group
            mode="out"
            leave-active-class="slide-out-leave-active"
            leave-to-class="slide-out-leave-to"
          >
            <h4 key="search-header" class="pa-2 font-weight-semibold">
              Saved Searches
            </h4>
            <div
              v-for="search in searches"
              :key="search.id"
              class="
                pa-2
                font--primary
                body
                search-item
                d-flex
                justify-space-between
              "
              :class="{
                disabled: loadingIds.includes(search.id),
                active: selectedSearch?.id == search.id
              }"
              tabindex="0"
              @click.self="
                media.md ? selectAndApply(search) : selectSearch(search)
              "
            >
              <div>{{ search.name }}</div>

              <IconButton
                flat
                icon="pi-delete-bin-line text--grey-20 pi-sm"
                :disabled="loadingIds.includes(search.id)"
                @click="remove(search.id)"
              />
            </div>
          </transition-group>
        </div>
      </transition>
    </div>

    <template v-if="!media.md" v-slot:actions>
      <CardActions class="pa-2 menu-actions d-flex align-center justify-end">
        <Button
          color="primary"
          height="35px"
          :width="!media.md ? '100%' : 'auto'"
          @click="applyFilter"
        >
          Apply
        </Button>
      </CardActions>
    </template>
  </Card>
</template>

<script lang="ts" setup>
import { ref, onBeforeMount, onBeforeUnmount } from 'vue'
import { Api, Endpoints } from '@/plugins/api'
import { showToast } from '@prefecthq/miter-design'
import { useStore } from 'vuex'
import media from '@/utilities/media'

const store = useStore()
const emit = defineEmits(['close'])

type SavedSearch = {
  name: string
  id: string
  filters: any
}

const selectedSearch = ref<SavedSearch>()
const searches = ref<SavedSearch[]>([])
const loadingIds = ref<string[]>([])
const error = ref()
const loading = ref()

const getSavedSearches = async () => {
  loading.value = true

  try {
    const query = Api.query({
      endpoint: Endpoints.saved_searches,
      options: { paused: true }
    })

    const res = await query.fetch()

    if (res.response.error) error.value = res.response.error
    else searches.value = res.response.value
  } catch (e) {
    error.value = e
  } finally {
    loading.value = false
    console.log(searches.value)
  }
}

const close = () => {
  emit('close')
}

const selectSearch = (search: SavedSearch) => {
  selectedSearch.value = search
}

const selectAndApply = (search: SavedSearch) => {
  selectSearch(search)
  applyFilter()
}

const applyFilter = () => {
  if (!selectedSearch.value) return
  const gf = { ...selectedSearch.value?.filters }

  if (gf.flow_runs?.timeframe?.from?.timestamp) {
    gf.flow_runs.timeframe.from.timestamp = new Date(
      gf.flow_runs.timeframe.from.timestamp
    )
  }
  if (gf.flow_runs?.timeframe?.to?.timestamp) {
    gf.flow_runs.timeframe.to.timestamp = new Date(
      gf.flow_runs.timeframe.to.timestamp
    )
  }
  if (gf.task_runs?.timeframe?.from?.timestamp) {
    gf.task_runs.timeframe.from.timestamp = new Date(
      gf.task_runs.timeframe.from.timestamp
    )
  }
  if (gf.task_runs?.timeframe?.to?.timestamp) {
    gf.task_runs.timeframe.to.timestamp = new Date(
      gf.task_runs.timeframe.to.timestamp
    )
  }

  store.commit('globalFilter', selectedSearch.value?.filters)
  emit('close')
}

// TODO: Add keyboard arrow navigation for search results (tab navigation works)
// const currentItem = ref<number>(0)
// const selectNextItem = (e: KeyboardEvent) => {
//   switch (e.key) {
//     case 'Down': // IE/Edge specific value
//     case 'ArrowDown':
//       if (currentItem.value > 0) currentItem.value--
//       else currentItem.value = searches.value.length - 1
//       break
//     case 'Up': // IE/Edge specific value
//     case 'ArrowUp':
//       if (currentItem.value < searches.value.length - 1) currentItem.value++
//       else currentItem.value = 0
//       break
//     default:
//       break
//   }
// }

onBeforeMount(() => {
  getSavedSearches()
  // window.addEventListener('keyup', selectNextItem)
})

onBeforeUnmount(() => {
  // window.removeEventListener('keyup', selectNextItem)
})

const remove = async (id: string) => {
  loadingIds.value.push(id)

  const query = await Api.query({
    endpoint: Endpoints.delete_search,
    body: {
      id: id
    },
    options: { paused: true }
  })

  const res = await query.fetch()

  showToast({
    type: res.error ? 'error' : 'success',
    message: res.error ? `Error: ${res.error}` : 'Search removed',
    timeout: 10000
  })

  await getSavedSearches()
  loadingIds.value.splice(loadingIds.value.indexOf(id), 1)
}
</script>

<style lang="scss" scoped>
@use '@prefecthq/miter-design/src/styles/abstracts/variables' as *;

.menu {
  border-radius: 0;
  position: relative;

  .menu-content {
    border-top: 1px solid $secondary-hover;
    border-radius: 0 !important;
    overscroll-behavior: contain;
    height: 100%;
    overflow: auto;

    @media (max-width: 640px) {
      width: 100%;
    }
  }

  .menu-actions {
    border-top: 1px solid $secondary-hover;
  }

  > ::v-deep(div) {
    border-radius: 0 0 3px 3px !important;
    max-height: inherit;
  }

  .menu-container {
    position: relative;
  }
}

.search-item {
  cursor: pointer;

  &.disabled {
    cursor: not-allowed;
    color: $grey-20 !important;
  }

  &.active {
    background-color: $blue-10;
    color: $primary;
  }

  .hovered,
  &:hover,
  &:focus {
    background-color: $blue-5;
    color: $primary;
    outline: none;

    ::v-deep(i) {
      color: $grey-40 !important;
    }
  }

  ::v-deep(i) {
    &:hover,
    &:focus {
      color: $error !important;
    }
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 500s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
.slide-out-enter-active,
.slide-out-leave-active {
  transition: transform 150ms ease;
}

.slide-out-enter-from,
.slide-out-leave-to {
  transform: translate(-100%);
}
</style>
