#include "mono_euroc.h"
namespace basalt {
DatasetIoInterfacePtr DatasetIoFactory::getDatasetIo(const std::string& type, bool load_gt) {
  if(type != "euroc") throw std::runtime_error("Mono runtime requires euroc input");
  std::cerr << "MONO_READER: exactly one camera, cam0" << std::endl;
  return DatasetIoInterfacePtr(new MonoEurocIO(load_gt));
}
}
