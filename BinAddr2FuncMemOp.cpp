/*BEGIN_LEGAL 
Intel Open Source License 

Copyright (c) 2002-2010 Intel Corporation. All rights reserved.
 
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

Redistributions of source code must retain the above copyright notice,
this list of conditions and the following disclaimer.  Redistributions
in binary form must reproduce the above copyright notice, this list of
conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.  Neither the name of
the Intel Corporation nor the names of its contributors may be used to
endorse or promote products derived from this software without
specific prior written permission.
 
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE INTEL OR
ITS CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
END_LEGAL */
#include <iomanip>
#include <iostream>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pin.H"

KNOB<string> KnobInputFile(KNOB_MODE_WRITEONCE, "pintool",
    "i", "<imagename>", "specify an image to read");

KNOB<unsigned long> knob_dec_address(KNOB_MODE_WRITEONCE, "pintool", "a", "0",
				    "address of an instruction in a routine");

KNOB<unsigned> knob_disassm_full(KNOB_MODE_WRITEONCE, "pintool", "l", "0",
			 "Disassemble entire binary image");

/* ===================================================================== */
/* Print Help Message                                                    */
/* ===================================================================== */

INT32 Usage()
{
    cerr << "This tool disassembles an image." << endl << endl;
    cerr << KNOB_BASE::StringKnobSummary();
    cerr << endl;
    return -1;
}

/* ===================================================================== */
/* Main                                                                  */
/* ===================================================================== */

int is_lea(std::string instr_string)
{
  std::string::size_type pos = instr_string.find_first_of(' ');
  std::string token = instr_string.substr(0, pos);

  if( token.compare("lea") == 0)
    return 1;
	    
  return 0;
}

int is_other_mov(std::string instr_string)
{
  std::string::size_type pos = instr_string.find_first_of(' ');
  std::string token = instr_string.substr(0, pos);

  if( token.compare("movsxd") == 0)
    return 1;
	    
  return 0;
}

int main(INT32 argc, CHAR **argv)
{
    PIN_InitSymbols();

    if( PIN_Init(argc,argv) )
    {
        return Usage();
    }
    
    IMG img = IMG_Open(KnobInputFile);

    if (!IMG_Valid(img))
    {
        std::cout << "Could not open " << KnobInputFile.Value() << endl;
        exit(1);
    }
    
    std::cout << hex;
    
    for (SEC sec = IMG_SecHead(img); SEC_Valid(sec); sec = SEC_Next(sec))
    {
      /*        std::cout << "Section: " << setw(8) << SEC_Address(sec) << " " << SEC_Name(sec) << endl; */
                
        for (RTN rtn = SEC_RtnHead(sec); RTN_Valid(rtn); rtn = RTN_Next(rtn))
        {
	  /*            std::cout << "  Rtn: " << setw(8) << RTN_Address(rtn) << " " << RTN_Name(rtn) << endl;
            string path;
            INT32 line;


            PIN_GetSourceLocation(RTN_Address(rtn), NULL, &line, &path);

            if (path != "")
            {
                std::cout << "File " << path << " Line " << line << endl; 
            }
	  */
            RTN_Open(rtn);

	    ADDRINT routineStartAddress = INS_Address(RTN_InsHead(rtn)); 
	    ADDRINT routineEndAddress = routineStartAddress + RTN_Size(rtn);
	    //	    ADDRINT insAddress = routineStartAddress;
        
        uint32_t FuncMemOps = 0;
        uint32_t FuncReadOps = 0;
        uint32_t FuncWriteOps = 0;
            
	    if( knob_disassm_full || (routineStartAddress <= knob_dec_address && routineEndAddress >= knob_dec_address) ){

	      for (INS ins = RTN_InsHead(rtn); INS_Valid(ins); ins = INS_Next(ins)){
		  
		    
		  //int num_rregs = INS_MaxNumRRegs(ins);
		  //int isLea = is_lea(INS_Disassemble(ins));
		  //int isOtherMov = is_other_mov(INS_Disassemble(ins));
		  
          if( INS_IsNop(ins) ){
              //std::cout << "instr:    " << setw(8) << INS_Address(ins) << " " << INS_Disassemble(ins) << endl;
              continue;
              }
              
		  else if( INS_IsMemoryRead(ins) || INS_IsMemoryWrite(ins)){
              
              FuncMemOps++;
              
              //std::cout << "instr:    " << setw(8) << INS_Address(ins) << " " << INS_Disassemble(ins) << endl;
              
              if( INS_IsMemoryRead(ins) ){
                  FuncReadOps++;
                  
                  if (knob_dec_address == INS_Address(ins))
                    std::cout << RTN_Name(rtn) << ":" << std::dec << FuncMemOps << ":r" << std::dec << FuncReadOps << std::endl;
                  
                  
              }
              else{
                  FuncWriteOps++;
                  
                  if (knob_dec_address == INS_Address(ins))
                    std::cout << RTN_Name(rtn) << ":" << std::dec << FuncMemOps << ":w" << std::dec << FuncReadOps << std::endl;
              }
              
//              if (knob_dec_address == INS_Address(ins)){
//                  //std::cout << "instr:    " << setw(8) << INS_Address(ins) << " " << INS_Disassemble(ins) << endl;
//                  for(int i = 0; i< num_rregs; i++)
//                  std::cout << "R:" << INS_RegR(ins, i) << "   ";
//                  
//                  int num_wregs = INS_MaxNumWRegs(ins);
//                  
//                  for(int i = 0; i< num_wregs; i++)
//                  std::cout << "W:" << INS_RegW(ins, i) << "   ";
//                  std::cout << endl;
//              }
          }

	      }
	    }

            RTN_Close(rtn);
        }
    }
    IMG_Close(img);
}
