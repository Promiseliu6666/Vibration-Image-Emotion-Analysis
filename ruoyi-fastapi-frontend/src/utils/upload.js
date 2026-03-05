// src/utils/upload.js
/**
 * 将 File 对象转为 base64 字符串
 * @param {File} file
 * @returns {Promise<string>}
 */
export function getBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.readAsDataURL(file.raw || file)  // Element Plus Upload 组件中 file 有 .raw 属性
      reader.onload = () => resolve(reader.result)
      reader.onerror = error => reject(error)
    })
  }