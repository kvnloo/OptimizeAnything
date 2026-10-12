// Adapter only. The unmodified Sindre Sorhus implementation lives in vendor/.
import {createInterface} from 'node:readline';
import leven from './vendor/index.mjs';

function decode(field) {
  if (field === '') return '';
  const words = field.split(',');
  if (words.length > 4096 || words.some(word => !/^[0-9a-fA-F]{4}$/.test(word))) {
    throw new Error('Expected at most 4096 four-digit UTF-16 hex units');
  }
  return String.fromCharCode(...words.map(word => Number.parseInt(word, 16)));
}

try {
  for await (const line of createInterface({input: process.stdin, crlfDelay: Infinity})) {
    const fields = line.split('\t');
    if (fields.length !== 2) throw new Error('Expected exactly two tab-separated fields');
    console.log(leven(decode(fields[0]), decode(fields[1])));
  }
} catch (error) {
  console.error(error.message);
  process.exitCode = 2;
}
