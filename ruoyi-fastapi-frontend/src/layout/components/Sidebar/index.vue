<template>
  <div :class="{ 'has-logo': showLogo }" class="sidebar-container">
    <logo v-if="showLogo" :collapse="isCollapse" />
    <el-scrollbar wrap-class="scrollbar-wrapper">
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :background-color="getMenuBackground"
        :text-color="getMenuTextColor"
        :unique-opened="true"
        :active-text-color="theme"
        :collapse-transition="false"
        mode="vertical"
        :class="sideTheme"
      >
        <sidebar-item
          v-for="(route, index) in sidebarRouters"
          :key="route.path + index"
          :item="route"
          :base-path="route.path"
        />
      </el-menu>
    </el-scrollbar>
  </div>
</template>

<script setup>
import Logo from './Logo'
import SidebarItem from './SidebarItem'
import variables from '@/assets/styles/variables.module.scss'
import useAppStore from '@/store/modules/app'
import useSettingsStore from '@/store/modules/settings'
import usePermissionStore from '@/store/modules/permission'

const route = useRoute();
const appStore = useAppStore()
const settingsStore = useSettingsStore()
const permissionStore = usePermissionStore()

const sidebarRouters = computed(() => permissionStore.sidebarRouters);
const showLogo = computed(() => settingsStore.sidebarLogo);
const sideTheme = computed(() => settingsStore.sideTheme);
const theme = computed(() => settingsStore.theme);
const isCollapse = computed(() => !appStore.sidebar.opened);

// 获取菜单背景色
const getMenuBackground = computed(() => {
  if (settingsStore.isDark) {
    return 'var(--sidebar-bg)';
  }
  return sideTheme.value === 'theme-dark' ? variables.menuBg : variables.menuLightBg;
});

// 获取菜单文字颜色
const getMenuTextColor = computed(() => {
  if (settingsStore.isDark) {
    return 'var(--sidebar-text)';
  }
  return sideTheme.value === 'theme-dark' ? variables.menuText : variables.menuLightText;
});

const activeMenu = computed(() => {
  const { meta, path } = route;
  if (meta.activeMenu) {
    return meta.activeMenu;
  }
  return path;
});
</script>

<style lang="scss" scoped>
  .sidebar-container {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    width: 210px;
    background-color: v-bind(getMenuBackground);
    transition: width 0.28s;
    overflow: hidden;
    box-shadow: 8px 0 32px rgba(0, 0, 0, 0.08);
    z-index: 1001;
  
    &.has-logo {
      // Logo 区域固定高度，菜单从下方开始
      .scrollbar-wrapper {
        height: calc(100% - 64px); // 64px 为 Logo 高度（可根据实际调整）
        margin-top: 64px;
      }
    }
  
    .scrollbar-wrapper {
      height: 100%;
      background-color: v-bind(getMenuBackground);
  
      :deep(.el-scrollbar__wrap) {
        overflow-x: hidden;
      }
    }
  
    .el-menu {
      border-right: none;
      height: 100%;
  
      :deep(.el-sub-menu) {
        .el-sub-menu__title {
          color: v-bind(getMenuTextColor);
          font-size: 15px;
          font-weight: 500;
          border-radius: 12px;
          margin: 4px 12px;
          transition: all 0.3s;
  
          &:hover {
            background: rgba(102, 126, 234, 0.12) !important;
            color: #667eea !important;
          }
  
          .el-sub-menu__icon-arrow {
            color: v-bind(getMenuTextColor);
          }
        }
  
        &.is-active > .el-sub-menu__title {
          background: linear-gradient(90deg, #667eea, #764ba2) !important;
          color: #fff !important;
  
          .el-sub-menu__icon-arrow {
            color: #fff !important;
          }
        }
      }
  
      :deep(.el-menu-item) {
        color: v-bind(getMenuTextColor);
        font-size: 15px;
        font-weight: 500;
        border-radius: 12px;
        margin: 4px 12px;
        height: 48px;
        line-height: 48px;
        transition: all 0.3s;
  
        &:hover {
          background: rgba(102, 126, 234, 0.12) !important;
          color: #667eea !important;
        }
  
        &.is-active {
          background: linear-gradient(90deg, #667eea, #764ba2) !important;
          color: #fff !important;
        }
      }
  
      // 折叠状态下的图标居中
      &--collapse {
        :deep(.el-sub-menu) {
          .el-sub-menu__title {
            margin: 4px 8px;
            text-align: center;
  
            .el-sub-menu__icon-arrow {
              display: none;
            }
          }
        }
  
        :deep(.el-menu-item) {
          margin: 4px 8px;
          text-align: center;
        }
      }
    }
  }
  </style>