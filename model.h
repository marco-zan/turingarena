/*
 * model.h
 *
 *  Created on: 22 gen 2017
 *      Author: max
 */

#ifndef MODEL_H_
#define MODEL_H_

#include <vector>
#include <string>
#include <unordered_map>

namespace Arena {

using std::vector;
using std::unordered_map;
using std::string;

enum BaseType {
	INT
};

struct ArraySpecification {

};

struct Variable {
	string name;
	BaseType base_type;
	vector<ArraySpecification> array_specifications;
};

struct DataBlock {
	unordered_map<string, Variable> variables;
};

struct AlgorithmFunction {
	string name;
	vector<Variable> parameters;

	void generate_code(std::ostream& out);
};

struct Algorithm {
	unordered_map<string, AlgorithmFunction> functions;
};

std::ostream& operator<< (std::ostream& out, const Algorithm& algorithm);

struct Interface {
	unordered_map<string, Algorithm> algorithms;
};

std::ostream& operator<< (std::ostream& out, const Interface& interface);

} // namespace Arena

#endif /* MODEL_H_ */
