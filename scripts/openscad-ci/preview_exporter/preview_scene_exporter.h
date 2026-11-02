// SPDX-License-Identifier: GPL-2.0-or-later
// Build-only adapter. OpenSCAD's original geometry evaluators and CSG products
// remain the sole source of preview geometry/Boolean semantics.
#pragma once

#include <cmath>
#include <iomanip>
#include <locale>
#include <map>
#include <memory>
#include <ostream>
#include <stdexcept>
#include <vector>

#include "core/CSGNode.h"
#include "core/CSGTreeEvaluator.h"
#include "core/Tree.h"
#include "geometry/GeometryEvaluator.h"
#include "geometry/PolySet.h"
#include "glview/preview/CSGTreeNormalizer.h"

// The JSON schema is deliberately independent of C++ ABI, pointer values and
// OpenGL. This is a reference/validation format, not the final binary IPC.
namespace scad_preview_exporter {

struct Term {
  size_t id;
  unsigned int flags;
};
struct Product {
  std::vector<Term> intersections;
  std::vector<Term> subtractions;
};
using ProductList = std::vector<Product>;

class SceneWriter {
 public:
  size_t registerLeaf(const std::shared_ptr<CSGLeaf>& leaf) {
    auto iter = instanceIds.find(leaf.get());
    if (iter != instanceIds.end()) return iter->second;
    if (!leaf->polyset || leaf->polyset->isEmpty())
      throw std::runtime_error("Preview product references empty PolySet");
    registerMesh(leaf->polyset);
    const size_t id = instances.size();
    instances.push_back(leaf);
    instanceIds.emplace(leaf.get(), id);
    return id;
  }

  ProductList group(const std::shared_ptr<CSGNode>& root, CSGTreeNormalizer& normalizer) {
    if (!root || root->isEmptySet()) return {};
    auto normalized = normalizer.normalize(root);
    if (!normalized || normalized->isEmptySet())
      throw std::runtime_error("OpenSCAD CSG normalization did not produce a valid tree");
    CSGProducts products;
    products.import(normalized);
    ProductList result;
    for (const auto& product : products.products) {
      if (product.intersections.empty()) continue;
      Product converted;
      for (const auto& term : product.intersections)
        converted.intersections.push_back({registerLeaf(term.leaf), static_cast<unsigned int>(term.flags)});
      for (const auto& term : product.subtractions)
        converted.subtractions.push_back({registerLeaf(term.leaf), static_cast<unsigned int>(term.flags)});
      result.push_back(std::move(converted));
    }
    return result;
  }

  void write(std::ostream& output, const ProductList& root, const ProductList& highlights,
             const ProductList& backgrounds) const {
    output.imbue(std::locale::classic());
    output << std::setprecision(17);
    output << "{\"schemaVersion\":1,\"source\":\"OpenSCAD CSGTreeEvaluator/CSGTreeNormalizer/CSGProducts\"";
    output << ",\"matrixOrder\":\"row-major\",\"meshes\":[";
    for (size_t i = 0; i < meshes.size(); ++i) {
      if (i) output << ',';
      const auto& mesh = *meshes[i];
      output << "{\"positions\":[";
      for (size_t j = 0; j < mesh.vertices.size(); ++j) {
        if (j) output << ',';
        output << '[';
        for (int axis = 0; axis < 3; ++axis) {
          if (axis) output << ',';
          numeric(output, mesh.vertices[j][axis]);
        }
        output << ']';
      }
      output << "],\"indices\":[";
      for (size_t j = 0; j < mesh.indices.size(); ++j) {
        if (j) output << ',';
        const auto& polygon = mesh.indices[j];
        if (polygon.size() != 3)
          throw std::runtime_error("Preview Scene requires pre-triangulated OpenSCAD PolySet facets");
        output << '[' << polygon[0] << ',' << polygon[1] << ',' << polygon[2] << ']';
      }
      output << "]}";
    }
    output << "],\"instances\":[";
    for (size_t i = 0; i < instances.size(); ++i) {
      if (i) output << ',';
      const auto& leaf = instances[i];
      output << "{\"mesh\":" << meshIds.at(leaf->polyset.get()) << ",\"matrix\":[";
      for (int row = 0; row < 4; ++row)
        for (int col = 0; col < 4; ++col) {
          if (row || col) output << ',';
          numeric(output, leaf->matrix.matrix()(row, col));
        }
      output << "],\"color\":[";
      for (int c = 0; c < 4; ++c) {
        if (c) output << ',';
        numeric(output, leaf->color[c]);
      }
      output << "],\"convexity\":" << leaf->polyset->getConvexity() << '}';
    }
    output << "],\"products\":";
    writeProducts(output, root);
    output << ",\"highlights\":";
    writeProducts(output, highlights);
    output << ",\"backgrounds\":";
    writeProducts(output, backgrounds);
    output << "}\n";
  }

 private:
  static void numeric(std::ostream& out, double value) {
    if (!std::isfinite(value))
      throw std::runtime_error("Preview Scene contains non-finite geometry or transform");
    out << value;
  }

  static void writeTerms(std::ostream& output, const std::vector<Term>& terms) {
    output << '[';
    for (size_t i = 0; i < terms.size(); ++i) {
      if (i) output << ',';
      output << "{\"id\":" << terms[i].id << ",\"flags\":" << terms[i].flags << '}';
    }
    output << ']';
  }

  static void writeProducts(std::ostream& output, const ProductList& products) {
    output << '[';
    for (size_t i = 0; i < products.size(); ++i) {
      if (i) output << ',';
      output << "{\"intersections\":";
      writeTerms(output, products[i].intersections);
      output << ",\"subtractions\":";
      writeTerms(output, products[i].subtractions);
      output << '}';
    }
    output << ']';
  }

  void registerMesh(const std::shared_ptr<const PolySet>& mesh) {
    if (meshIds.count(mesh.get())) return;
    meshIds.emplace(mesh.get(), meshes.size());
    meshes.push_back(mesh);
  }

  std::map<const CSGLeaf *, size_t> instanceIds;
  std::map<const PolySet *, size_t> meshIds;
  std::vector<std::shared_ptr<CSGLeaf>> instances;
  std::vector<std::shared_ptr<const PolySet>> meshes;
};

inline void exportScene(const Tree& tree, const AbstractNode& root, std::ostream& output) {
  GeometryEvaluator geometry(tree);
  CSGTreeEvaluator evaluator(tree, &geometry);
  auto rootTerm = evaluator.buildCSGTree(root);
  CSGTreeNormalizer normalizer(100000);
  SceneWriter writer;
  const auto mainProducts = writer.group(rootTerm, normalizer);
  ProductList highlightProducts;
  for (const auto& node : evaluator.getHighlightNodes()) {
    auto next = writer.group(node, normalizer);
    highlightProducts.insert(highlightProducts.end(), next.begin(), next.end());
  }
  ProductList backgroundProducts;
  for (const auto& node : evaluator.getBackgroundNodes()) {
    auto next = writer.group(node, normalizer);
    backgroundProducts.insert(backgroundProducts.end(), next.begin(), next.end());
  }
  writer.write(output, mainProducts, highlightProducts, backgroundProducts);
}
}  // namespace scad_preview_exporter
